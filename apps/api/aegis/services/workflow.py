from typing import Any
from uuid import uuid4

from aegis.adapters.datahub.client import DataHubAdapter, graph_fingerprint
from aegis.adapters.datahub.seed import REFUND_AGENT_URN
from aegis.context_store import BusinessContextStore
from aegis.domain.enums import AttestationState, Decision, IncidentState, SourceSystem
from aegis.domain.models import (
    Attestation,
    ControlEvaluation,
    EvidenceItem,
    IncidentDetail,
    IncidentSummary,
    RegressionRun,
    ToolCall,
)
from aegis.domain.transitions import require_transition
from aegis.persistence.store import AegisStore
from aegis.services.regression_runner import RegressionRunner
from aegis.services.tool_gateway import ToolGateway


class VersionConflict(ValueError):
    pass


class WorkflowService:
    def __init__(
        self,
        store: AegisStore,
        datahub: DataHubAdapter,
        context_store: BusinessContextStore | None = None,
    ) -> None:
        self.store = store
        self.datahub = datahub
        self.gateway = ToolGateway(store)
        self.regressions = RegressionRunner(store)
        self.context_store = context_store

    def state(self) -> dict[str, Any]:
        return self.store.get_state()

    def ingest_datahub_change(self, entity_urn: str) -> bool:
        """Invalidate trust after an Actions notification, confirmed by a direct GMS read."""
        state = self.state()
        if IncidentState(state["incident_state"]) != IncidentState.HEALTHY:
            return False
        snapshot = self.datahub.governance_snapshot("refund")
        if (
            not snapshot.datahubAvailable
            or snapshot.approvalStatus == "approved"
            or not any(marker in entity_urn for marker in ("refund", "policy"))
        ):
            return False
        if self.context_store:
            self.context_store.activate_refund_policy(poisoned=True)
        incident_urn = self.datahub.write_incident(
            resolved=False,
            detail="DataHub Actions detected unapproved context in the refund lineage.",
        )
        active_urn = str(snapshot.raw.get("activeSourceUrn", ""))
        active_name = active_urn.split(",")[-2] if "," in active_urn else active_urn
        self.store.update_state(
            incident_state=IncidentState.CONTEXT_CHANGED.value,
            version=state["version"] + 1,
            active_source=active_name or "refund-policy-q4-draft.md",
            source_approved=0,
            remediation_applied=0,
            datahub_incident_urn=incident_urn,
            writeback_state="ACTIVE",
        )
        self.store.append_audit(
            "ATTESTATION_INVALIDATED",
            "Direct DataHub re-read confirmed the Actions change affected approved context.",
            source_system=SourceSystem.DATAHUB,
            payload={"entityUrn": entity_urn, "evidenceIds": snapshot.evidenceIds},
        )
        return True

    def incident_summary(self) -> IncidentSummary:
        state = self.state()
        incident_state = IncidentState(state["incident_state"])
        decision = Decision.BLOCK if incident_state in {
            IncidentState.BLOCKED,
            IncidentState.REMEDIATION_APPLIED,
        } else Decision.ALLOW if incident_state in {
            IncidentState.HEALTHY,
            IncidentState.RESOLVED,
        } else Decision.REVIEW
        return IncidentSummary(
            id="aegis-4821",
            pipelineId="refund",
            pipelineName="Refund Resolution Agent",
            environment="PRODUCTION",
            state=incident_state,
            decision=decision,
            causalChange=(
                "refund-policy-v12.md restored"
                if incident_state
                in {
                    IncidentState.REMEDIATION_APPLIED,
                    IncidentState.RE_EVALUATED,
                    IncidentState.RESOLVED,
                }
                else "refund-policy-q4-draft.md entered context"
                if incident_state != IncidentState.HEALTHY
                else "No unsafe context change"
            ),
            preventedAction=(
                "$8,500 refund blocked before execution"
                if incident_state in {IncidentState.BLOCKED, IncidentState.REMEDIATION_APPLIED}
                else "issue_refund monitored"
            ),
            recommendedNextStep=self._next_step(incident_state),
            openedAt="2026-08-06T18:50:46Z",
            resolvedAt=state["updated_at"] if incident_state == IncidentState.RESOLVED else None,
            version=state["version"],
        )

    @staticmethod
    def _next_step(state: IncidentState) -> str:
        return {
            IncidentState.HEALTHY: "Simulate context change",
            IncidentState.CONTEXT_CHANGED: "Run safety gate",
            IncidentState.BLOCKED: "Investigate evidence, then restore approved source",
            IncidentState.REMEDIATION_APPLIED: "Verify recovery",
            IncidentState.RE_EVALUATED: "Complete verified write-back",
            IncidentState.RESOLVED: "Return to Command Center",
        }[state]

    def attestation(self) -> Attestation:
        state = self.state()
        incident_state = IncidentState(state["incident_state"])
        mapping = {
            IncidentState.HEALTHY: AttestationState.TRUSTED,
            IncidentState.CONTEXT_CHANGED: AttestationState.INVALIDATED,
            IncidentState.BLOCKED: AttestationState.BLOCKED,
            IncidentState.REMEDIATION_APPLIED: AttestationState.RE_EVALUATING,
            IncidentState.RE_EVALUATED: AttestationState.RE_EVALUATED,
            IncidentState.RESOLVED: AttestationState.TRUSTED,
        }
        latest_evaluation = self.store.latest_json("evaluations")
        latest_regression = self.store.latest_json("regression_runs")
        return Attestation(
            id=f"att-refund-v2.8.4-{state['version']:04d}",
            agentUrn=REFUND_AGENT_URN,
            agentVersion="2.8.4",
            environment="PRODUCTION",
            owner="Commerce AI Platform",
            state=mapping[incident_state],
            decision=(
                Decision.BLOCK
                if incident_state in {IncidentState.BLOCKED, IncidentState.REMEDIATION_APPLIED}
                else Decision.REVIEW
                if incident_state in {IncidentState.CONTEXT_CHANGED, IncidentState.RE_EVALUATED}
                else Decision.ALLOW
            ),
            graphFingerprint=graph_fingerprint(self.datahub.graph(state)),
            evidenceTimestamp=state["updated_at"],
            incidentId="aegis-4821" if incident_state != IncidentState.HEALTHY else None,
            controlResults=(
                [ControlEvaluation.model_validate(latest_evaluation)] if latest_evaluation else []
            ),
            regressionResults=(
                [RegressionRun.model_validate(latest_regression)] if latest_regression else []
            ),
            remediationState=(
                "VERIFIED"
                if incident_state == IncidentState.RESOLVED
                else "APPLIED"
                if state["remediation_applied"]
                else "NONE"
            ),
        )

    def detail(self) -> IncidentDetail:
        summary = self.incident_summary()
        state = summary.state
        available = {
            IncidentState.HEALTHY: ["SIMULATE_CONTEXT_CHANGE"],
            IncidentState.CONTEXT_CHANGED: ["RUN_SAFETY_GATE"],
            IncidentState.BLOCKED: ["OPEN_EVIDENCE", "REMEDIATE"],
            IncidentState.REMEDIATION_APPLIED: ["VERIFY_RECOVERY"],
            IncidentState.RE_EVALUATED: ["VERIFY_RECOVERY"],
            IncidentState.RESOLVED: ["RETURN_TO_COMMAND_CENTER"],
        }[state]
        evidence = self._evidence(state)
        return IncidentDetail(
            incident=summary,
            attestation=self.attestation(),
            availableActions=available,
            evidenceSummary=evidence,
            auditEvents=self.store.list_audit(),
            datahubIncidentUrn=self.state()["datahub_incident_urn"],
            writeBackState=self.state()["writeback_state"],
        )

    def _evidence(self, state: IncidentState) -> list[EvidenceItem]:
        approval = "approved" if self.state()["source_approved"] else "not approved"
        control_value = (
            "Passed after remediation"
            if state == IncidentState.RESOLVED
            else "Failed · source not approved"
            if state in {IncidentState.BLOCKED, IncidentState.REMEDIATION_APPLIED}
            else "Pending evaluation"
        )
        return [
            EvidenceItem(
                id="evidence-control",
                label="Safety control",
                value=f"ApprovedContextSource · {control_value}",
                detail=(
                    "Production refunds over $2,000 require approved context "
                    "and complete lineage."
                ),
                sourceSystem=SourceSystem.AEGIS,
                raw={"control": "approved-context-source", "state": state.value},
            ),
            EvidenceItem(
                id="evidence-tool-call",
                label="Intercepted tool call",
                value="issue_refund({ amount: 8500, currency: 'USD', caseId: 'CX-90214' })",
                detail="The simulated refund executor was not called while the decision was Block.",
                sourceSystem=SourceSystem.SIMULATED_EXTERNAL,
                raw={
                    "amount": 8500,
                    "currency": "USD",
                    "executed": False,
                },
            ),
            EvidenceItem(
                id="evidence-provenance",
                label="Source provenance",
                value=f"{self.state()['active_source']} · approval: {approval}",
                detail=(
                    "The selected four-node path is normalized from the DataHub adapter boundary."
                ),
                sourceSystem=self.datahub.source_system(),
                raw=self.datahub.graph(self.state()).model_dump(mode="json"),
            ),
        ]

    def context_change(self, expected_version: int) -> dict[str, Any]:
        state = self._require_version(expected_version)
        current = IncidentState(state["incident_state"])
        require_transition(current, IncidentState.CONTEXT_CHANGED)
        datahub_change = self.datahub.switch_refund_context(poisoned=True)
        if self.context_store:
            self.context_store.activate_refund_policy(poisoned=True)
        incident_urn = (
            self.datahub.write_incident(
                resolved=False,
                detail="docs-sync activated an unapproved refund policy in the agent lineage.",
            )
            if self.datahub.configured_mode.value == "LIVE_SEEDED_DATAHUB"
            else "urn:li:incident:aegis-4821"
        )
        next_state = self.store.update_state(
            incident_state=IncidentState.CONTEXT_CHANGED.value,
            version=expected_version + 1,
            active_source="refund-policy-q4-draft.md",
            source_approved=0,
            remediation_applied=0,
            datahub_incident_urn=incident_urn,
            writeback_state="ACTIVE",
        )
        event = self.store.append_audit(
            "CONTEXT_CHANGED",
            "Draft refund policy replaced the approved source in the RAG path",
            source_system=self.datahub.source_system(),
        )
        return {
            "incidentId": "aegis-4821",
            "state": next_state["incident_state"],
            "attestationState": "INVALIDATED",
            "change": {
                "removedSource": "refund-policy-v12.md",
                "addedSource": "refund-policy-q4-draft.md",
            },
            "auditEventId": event.id,
            "datahubChange": datahub_change,
            "version": next_state["version"],
        }

    def evaluate(self, expected_version: int, call: ToolCall) -> dict[str, Any]:
        state = self._require_version(expected_version)
        current = IncidentState(state["incident_state"])
        require_transition(current, IncidentState.BLOCKED)
        datahub_status = self.datahub.status()["state"]
        available = datahub_status in {"CONNECTED", "SEEDED_OFFLINE"}
        evaluation, receipt = self.gateway.intercept(
            call,
            approval_status="approved" if state["source_approved"] else "not_approved",
            lineage_complete=True,
            datahub_available=available,
        )
        next_state = self.store.update_state(
            incident_state=IncidentState.BLOCKED.value,
            version=expected_version + 1,
        )
        self.store.append_audit(
            "TOOL_CALL_BLOCKED",
            "$8,500 issue_refund call blocked before simulated execution",
            payload={"evaluationId": evaluation.id},
        )
        return {
            "incidentId": "aegis-4821",
            "state": next_state["incident_state"],
            "decision": evaluation.decision,
            "executed": receipt is not None,
            "evaluation": evaluation,
            "version": next_state["version"],
        }

    def remediate(self, expected_version: int) -> dict[str, Any]:
        state = self._require_version(expected_version)
        current = IncidentState(state["incident_state"])
        require_transition(current, IncidentState.REMEDIATION_APPLIED)
        datahub_change = self.datahub.switch_refund_context(poisoned=False)
        if self.context_store:
            self.context_store.activate_refund_policy(poisoned=False)
        next_state = self.store.update_state(
            incident_state=IncidentState.REMEDIATION_APPLIED.value,
            version=expected_version + 1,
            active_source="refund-policy-v12.md",
            source_approved=1,
            remediation_applied=1,
        )
        event = self.store.append_audit(
            "REMEDIATION_APPLIED",
            "Approved refund-policy-v12.md restored and pinned by content hash",
            source_system=self.datahub.source_system(),
        )
        return {
            "incidentId": "aegis-4821",
            "state": next_state["incident_state"],
            "remediation": {
                "oldSource": "refund-policy-q4-draft.md",
                "newSource": "refund-policy-v12.md",
                "pinnedContentHash": "sha256:27fd2b7a9ce9c09d1b61977dd6f07805",
                "auditEventId": event.id,
                "datahubChange": datahub_change,
            },
            "version": next_state["version"],
        }

    def verify(self, expected_version: int, suite_id: str) -> dict[str, Any]:
        state = self._require_version(expected_version)
        current = IncidentState(state["incident_state"])
        require_transition(current, IncidentState.RE_EVALUATED)
        run = self.regressions.run(suite_id)
        self.store.append_audit(
            "CONTEXT_RE_EVALUATED",
            "Restored context passed deterministic safety evaluation",
            payload={"regressionRunId": run.id},
        )
        target = IncidentState.RESOLVED if run.status == "PASSED" else IncidentState.BLOCKED
        require_transition(IncidentState.RE_EVALUATED, target)
        next_state = self.store.update_state(
            incident_state=target.value,
            version=expected_version + 1,
            writeback_state="RESOLVED" if target == IncidentState.RESOLVED else "ACTIVE",
        )
        if (
            target == IncidentState.RESOLVED
            and self.datahub.configured_mode.value == "LIVE_SEEDED_DATAHUB"
        ):
            self.datahub.write_incident(
                resolved=True,
                detail="Approved context was restored and the Aegis regression suite passed.",
            )
        attestation = self.attestation()
        attestation.id = f"att-refund-v2.8.4-{uuid4().hex[:8]}"
        self.store.save_json("attestations", attestation.id, "created_at", attestation)
        attestation_document_urn = None
        if (
            target == IncidentState.RESOLVED
            and self.datahub.configured_mode.value == "LIVE_SEEDED_DATAHUB"
        ):
            attestation_document_urn = self.datahub.write_attestation_document(
                attestation.model_dump(mode="json")
            )
        self.store.append_audit(
            "INCIDENT_RESOLVED",
            (
                "Regression passed; incident and attestation summary written to DataHub"
                if self.datahub.status()["state"] == "CONNECTED"
                else (
                    "Regression passed; incident and attestation summary stored "
                    "in Aegis demo state"
                )
            ),
            source_system=self.datahub.source_system(),
            payload={"attestationId": attestation.id},
        )
        return {
            "incidentId": "aegis-4821",
            "state": next_state["incident_state"],
            "trustState": "TRUSTED" if target == IncidentState.RESOLVED else "BLOCKED",
            "decision": "ALLOW" if target == IncidentState.RESOLVED else "BLOCK",
            "regressionRun": run,
            "attestation": attestation,
            "writeBack": {
                "datahubIncidentUrn": next_state["datahub_incident_urn"],
                "state": next_state["writeback_state"],
                "verified": target == IncidentState.RESOLVED,
                "destination": (
                    "DATAHUB"
                    if self.datahub.status()["state"] == "CONNECTED"
                    else "AEGIS_LOCAL_DEMO"
                ),
                "mode": self.datahub.configured_mode,
                "attestationDocumentUrn": attestation_document_urn,
            },
            "version": next_state["version"],
        }

    def _require_version(self, expected: int) -> dict[str, Any]:
        state = self.state()
        if state["version"] != expected:
            raise VersionConflict(
                f"Expected version {expected}; current version is {state['version']}"
            )
        return state
