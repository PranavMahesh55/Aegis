import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

import httpx

from aegis.adapters.datahub.seed import (
    PIPELINES,
    POLICY_APPROVED_URN,
    POLICY_DRAFT_URN,
    REFUND_AGENT_URN,
    REFUND_RAG_URN,
    REFUND_TOOL_URN,
    RISK_FEATURES_URN,
)
from aegis.config import Settings
from aegis.domain.enums import (
    DataMode,
    GraphStatus,
    IncidentState,
    Relationship,
    SourceSystem,
    TrustState,
)
from aegis.domain.models import (
    AgentRun,
    CatalogEvidenceSnapshot,
    Dependency,
    EdgeEvidence,
    GraphEdge,
    GraphNode,
    GraphProjection,
    IncidentLink,
    PipelineSummary,
    Provenance,
)


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def graph_fingerprint(graph: GraphProjection) -> str:
    encoded = json.dumps(graph.model_dump(mode="json"), sort_keys=True).encode()
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


class DataHubAdapter:
    """Boundary for catalog facts.

    Seeded mode is deliberately labeled and never presented as a successful live query.
    Live mode probes GMS and uses the same deterministic seed identities; the companion
    seed script is responsible for emitting and verifying them in DataHub.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def configured_mode(self) -> DataMode:
        return (
            DataMode.LIVE_SEEDED_DATAHUB
            if self.settings.data_mode.lower() == "live"
            else DataMode.SEEDED_DEMO
        )

    def status(self) -> dict[str, Any]:
        if self.configured_mode == DataMode.SEEDED_DEMO:
            return {
                "state": "SEEDED_OFFLINE",
                "instance": "deterministic-aegis-seed",
                "serverVersion": None,
                "lastSuccessfulQueryAt": None,
                "detail": "Seeded demonstration metadata; no live DataHub query is claimed.",
            }
        try:
            response = httpx.get(
                f"{self.settings.datahub_gms_url.rstrip('/')}/config",
                headers=self._headers(),
                timeout=2.0,
            )
            response.raise_for_status()
            config = response.json()
            return {
                "state": "CONNECTED",
                "instance": self.settings.datahub_gms_url,
                "serverVersion": (
                    config.get("versions", {}).get("acryldatahub")
                    or config.get("versions", {}).get("acryldata/datahub", {}).get("version")
                ),
                "lastSuccessfulQueryAt": utc_now(),
                "detail": "Live DataHub GMS probe succeeded.",
            }
        except (httpx.HTTPError, ValueError) as error:
            return {
                "state": "DEGRADED",
                "instance": self.settings.datahub_gms_url,
                "serverVersion": None,
                "lastSuccessfulQueryAt": None,
                "detail": f"Live DataHub unavailable: {type(error).__name__}",
            }

    def _headers(self) -> dict[str, str]:
        return (
            {"Authorization": f"Bearer {self.settings.datahub_gms_token}"}
            if self.settings.datahub_gms_token
            else {}
        )

    def _aspect(self, urn: str, aspect: str) -> dict[str, Any] | None:
        """Read an aspect directly from GMS; this is the enforcement-time re-read."""
        encoded = quote(urn, safe="")
        response = httpx.get(
            f"{self.settings.datahub_gms_url.rstrip('/')}/aspects/{encoded}",
            # Rest.li requires an explicit version for current-aspect reads.
            params={"aspect": aspect, "version": 0},
            headers=self._headers(),
            timeout=5.0,
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        payload = response.json()
        value = payload.get("aspect", payload.get("value", payload))
        if isinstance(value, dict) and len(value) == 1:
            only_key, only_value = next(iter(value.items()))
            if "." in only_key and isinstance(only_value, dict):
                value = only_value
        return value if isinstance(value, dict) else None

    def _emit_aspect(
        self, *, entity_type: str, urn: str, aspect_name: str, aspect: dict[str, Any]
    ) -> None:
        proposal = {
            "proposal": {
                "entityType": entity_type,
                "entityUrn": urn,
                "changeType": "UPSERT",
                "aspectName": aspect_name,
                "aspect": {
                    "value": json.dumps(aspect, separators=(",", ":")),
                    "contentType": "application/json",
                },
            }
        }
        response = httpx.post(
            f"{self.settings.datahub_gms_url.rstrip('/')}/aspects?action=ingestProposal",
            headers={**self._headers(), "Content-Type": "application/json"},
            json=proposal,
            timeout=10.0,
        )
        if response.is_error:
            raise RuntimeError(
                f"DataHub rejected {entity_type}/{aspect_name} with HTTP "
                f"{response.status_code}: {response.text[:1000]}"
            )

    def switch_refund_context(self, *, poisoned: bool) -> dict[str, Any]:
        """Change the real DataHub lineage edge used as active retrieval provenance."""
        if self.configured_mode != DataMode.LIVE_SEEDED_DATAHUB:
            return {"mode": "FIXTURE_ONLY", "changed": False}
        target = POLICY_DRAFT_URN if poisoned else POLICY_APPROVED_URN
        current = self._aspect(REFUND_RAG_URN, "upstreamLineage") or {}
        retained = [
            edge
            for edge in current.get("upstreams", [])
            if edge.get("dataset") not in {POLICY_APPROVED_URN, POLICY_DRAFT_URN}
        ]
        retained.append({"dataset": target, "type": "TRANSFORMED"})
        self._emit_aspect(
            entity_type="dataset",
            urn=REFUND_RAG_URN,
            aspect_name="upstreamLineage",
            aspect={"upstreams": retained, "fineGrainedLineages": []},
        )
        self.record_operation(
            REFUND_RAG_URN,
            "docs-sync",
            custom_properties={"activeSource": target, "poisoned": str(poisoned).lower()},
        )
        return {"mode": "LIVE_DATAHUB", "changed": True, "activeSourceUrn": target}

    def record_operation(
        self, urn: str, operation_type: str, *, custom_properties: dict[str, str] | None = None
    ) -> str:
        timestamp_ms = int(datetime.now(UTC).timestamp() * 1000)
        self._emit_aspect(
            entity_type="dataset",
            urn=urn,
            aspect_name="operation",
            aspect={
                "timestampMillis": timestamp_ms,
                "operationType": "CUSTOM",
                "lastUpdatedTimestamp": timestamp_ms,
                "customOperationType": operation_type,
                "customProperties": custom_properties or {},
            },
        )
        return f"operation:{urn}:{timestamp_ms}"

    def write_incident(self, *, resolved: bool, detail: str) -> str:
        urn = "urn:li:incident:aegis-4821"
        timestamp_ms = int(datetime.now(UTC).timestamp() * 1000)
        audit_stamp = {"time": timestamp_ms, "actor": "urn:li:corpuser:aegis"}
        self._emit_aspect(
            entity_type="incident",
            urn=urn,
            aspect_name="incidentInfo",
            aspect={
                "type": "CUSTOM",
                "customType": "AEGIS_CONTEXT_SAFETY",
                "title": "Unsafe refund context reached a production agent",
                "description": detail,
                "entities": [REFUND_AGENT_URN, REFUND_RAG_URN],
                "status": {
                    "state": "RESOLVED" if resolved else "ACTIVE",
                    "stage": "FIXED" if resolved else "INVESTIGATION",
                    "message": detail,
                    "lastUpdated": audit_stamp,
                },
                "priority": 1,
                "startedAt": timestamp_ms,
                "created": audit_stamp,
            },
        )
        return urn

    def write_run_incident(self, run: AgentRun) -> str:
        """Publish a blocked or review run as a first-class DataHub incident."""
        if self.configured_mode != DataMode.LIVE_SEEDED_DATAHUB:
            raise RuntimeError("Run incidents require live DataHub mode")
        if run.gateDecision is None or run.proposedToolCall is None:
            raise ValueError("A run incident requires a gate decision and tool proposal")
        if run.gateDecision.decision.value not in {"BLOCK", "REVIEW"}:
            raise ValueError("Only blocked or review runs can be written as incidents")

        record = self.find_pipeline(run.pipelineId)
        if record is None:
            raise ValueError(f"Unknown pipeline: {run.pipelineId}")
        context_urn = REFUND_RAG_URN if run.pipelineId == "refund" else RISK_FEATURES_URN
        timestamp_ms = int(datetime.now(UTC).timestamp() * 1000)
        audit_stamp = {"time": timestamp_ms, "actor": "urn:li:corpuser:aegis"}
        decision = run.gateDecision.decision.value
        tool = str(run.proposedToolCall.get("tool", record["tool"]))
        urn = f"urn:li:incident:aegis-{run.id}"
        detail = (
            f"Aegis run {run.id} held the proposed {tool} call with decision {decision}. "
            f"Control {run.gateDecision.controlId} returned "
            f"{run.gateDecision.reasonCode}. Subject: {run.subject.type}/{run.subject.id}. "
            f"Evidence: {', '.join(run.gateDecision.evidenceSnapshot.evidenceIds) or 'none'}."
        )
        self._emit_aspect(
            entity_type="incident",
            urn=urn,
            aspect_name="incidentInfo",
            aspect={
                "type": "CUSTOM",
                "customType": "AEGIS_AGENT_RUN_SECURITY",
                "title": f"Aegis {decision.lower()} · {record['name']} · {run.id}",
                "description": detail,
                # Core 1.7 incident associations accept the Agent and Dataset here,
                # but reject API URNs. The proposed tool remains explicit in the
                # incident description and the run-level Aegis trace.
                "entities": [record["agentUrn"], context_urn],
                "status": {
                    "state": "ACTIVE",
                    "stage": "INVESTIGATION",
                    "message": detail,
                    "lastUpdated": audit_stamp,
                },
                "priority": 1 if decision == "BLOCK" else 2,
                "startedAt": timestamp_ms,
                "created": audit_stamp,
            },
        )
        return urn

    def write_run_attestation_document(self, run: AgentRun) -> str:
        """Publish an allowed consequential run as a DataHub attestation Document."""
        if self.configured_mode != DataMode.LIVE_SEEDED_DATAHUB:
            raise RuntimeError("Run attestations require live DataHub mode")
        if run.gateDecision is None or run.proposedToolCall is None:
            raise ValueError("A run attestation requires a gate decision and tool proposal")
        if run.gateDecision.decision.value != "ALLOW" or run.toolReceipt is None:
            raise ValueError("Only allowed, executed runs can be attested")
        try:
            from datahub.ingestion.graph.client import DataHubGraph
            from datahub.ingestion.graph.config import DatahubClientConfig
            from datahub.sdk import Document
            from datahub.sdk.main_client import DataHubClient
        except ImportError as error:
            raise RuntimeError("DataHub SDK is not installed") from error

        record = self.find_pipeline(run.pipelineId)
        if record is None:
            raise ValueError(f"Unknown pipeline: {run.pipelineId}")
        context_urn = REFUND_RAG_URN if run.pipelineId == "refund" else RISK_FEATURES_URN
        evidence = run.gateDecision.evidenceSnapshot
        evidence_fingerprint = "sha256:" + hashlib.sha256(
            json.dumps(evidence.model_dump(mode="json"), sort_keys=True).encode()
        ).hexdigest()
        tool = str(run.proposedToolCall.get("tool", record["tool"]))
        document_id = f"aegis-run-attestation-{run.id}"
        text = (
            "# Aegis run-level security attestation\n\n"
            f"- Run: `{run.id}`\n"
            f"- Agent: `{record['agentUrn']}`\n"
            f"- Subject: `{run.subject.type}/{run.subject.id}`\n"
            f"- Proposed tool: `{tool}`\n"
            "- Decision: **ALLOW**\n"
            f"- Control: `{run.gateDecision.controlId}`\n"
            f"- Reason: `{run.gateDecision.reasonCode}`\n"
            f"- Evidence fingerprint: `{evidence_fingerprint}`\n"
            f"- Evidence IDs: `{', '.join(evidence.evidenceIds) or 'none'}`\n"
            f"- Executor receipt: `{run.toolReceipt.get('id', 'recorded')}`\n"
            f"- Completed: `{run.completedAt or run.updatedAt}`\n"
        )
        document = Document.create_document(
            id=document_id,
            title=f"Aegis run attestation · {record['name']} · {run.id}",
            text=text,
            subtype="ATTESTATION",
            related_assets=[context_urn],
            owners=["urn:li:corpGroup:aegis-platform"],
            domain="urn:li:domain:agentic-systems",
            tags=["urn:li:tag:AgentGoverned"],
            custom_properties={
                "aegisRunId": run.id,
                "agentUrn": record["agentUrn"],
                "decision": "ALLOW",
                "controlId": run.gateDecision.controlId,
                "reasonCode": run.gateDecision.reasonCode,
                "proposedTool": tool,
                "subject": f"{run.subject.type}/{run.subject.id}",
                "evidenceFingerprint": evidence_fingerprint,
            },
        )
        graph = DataHubGraph(
            DatahubClientConfig(
                server=self.settings.datahub_gms_url,
                token=self.settings.datahub_gms_token or None,
            )
        )
        DataHubClient(graph=graph).entities.upsert(document)
        return f"urn:li:document:{document_id}"

    def write_attestation_document(self, attestation: dict[str, Any]) -> str:
        """Publish the compact trusted attestation to DataHub's document graph."""
        if self.configured_mode != DataMode.LIVE_SEEDED_DATAHUB:
            raise RuntimeError("Attestation Documents require live DataHub mode")
        try:
            from datahub.ingestion.graph.client import DataHubGraph
            from datahub.ingestion.graph.config import DatahubClientConfig
            from datahub.sdk import Document
            from datahub.sdk.main_client import DataHubClient
        except ImportError as error:
            raise RuntimeError("DataHub SDK is not installed") from error
        document_id = f"aegis-attestation-{attestation['id']}"
        text = (
            "# Trusted Aegis context attestation\n\n"
            f"- Agent: `{attestation['agentUrn']}`\n"
            f"- Version: `{attestation['agentVersion']}`\n"
            f"- Decision: **{attestation['decision']}**\n"
            f"- Graph fingerprint: `{attestation['graphFingerprint']}`\n"
            f"- Evidence timestamp: `{attestation['evidenceTimestamp']}`\n"
            f"- Supersedes incident: `{attestation.get('incidentId')}`\n"
        )
        document = Document.create_document(
            id=document_id,
            title=f"Aegis attestation · Refund Resolution Agent · {attestation['id']}",
            text=text,
            subtype="ATTESTATION",
            # Document relatedAssets does not currently accept aiAgent URNs.
            related_assets=[REFUND_RAG_URN],
            owners=["urn:li:corpGroup:aegis-platform"],
            domain="urn:li:domain:agentic-systems",
            tags=["urn:li:tag:AgentGoverned"],
            custom_properties={
                "aegisAttestationId": attestation["id"],
                "decision": attestation["decision"],
                "graphFingerprint": attestation["graphFingerprint"],
            },
        )
        graph = DataHubGraph(
            DatahubClientConfig(
                server=self.settings.datahub_gms_url,
                token=self.settings.datahub_gms_token or None,
            )
        )
        DataHubClient(graph=graph).entities.upsert(document)
        return f"urn:li:document:{document_id}"

    @staticmethod
    def _custom_property(properties: dict[str, Any] | None, key: str) -> str | None:
        if not properties:
            return None
        custom = properties.get("customProperties", properties.get("custom_properties", {}))
        if isinstance(custom, list):
            for item in custom:
                if item.get("key") == key:
                    return item.get("value")
        if isinstance(custom, dict):
            value = custom.get(key)
            return str(value) if value is not None else None
        return None

    def _latest_operation(self, urn: str) -> dict[str, Any] | None:
        response = httpx.post(
            f"{self.settings.datahub_gms_url.rstrip('/')}/aspects"
            "?action=getTimeseriesAspectValues",
            headers={**self._headers(), "Content-Type": "application/json"},
            json={
                "urn": urn,
                "entity": "dataset",
                "aspect": "operation",
                "limit": 1,
                "filter": {"or": [{"and": []}]},
            },
            timeout=5.0,
        )
        response.raise_for_status()
        values = response.json().get("value", {}).get("values", [])
        if not values:
            return None
        aspect = values[0].get("aspect", {}).get("value")
        return json.loads(aspect) if isinstance(aspect, str) else aspect

    def governance_snapshot(
        self, pipeline_id: str, *, observed_at: str | None = None
    ) -> CatalogEvidenceSnapshot:
        """Build fail-closed evidence from direct DataHub reads, never from Actions state."""
        captured = utc_now()
        if self.configured_mode != DataMode.LIVE_SEEDED_DATAHUB:
            return CatalogEvidenceSnapshot(
                capturedAt=captured,
                datahubAvailable=False,
                lineageComplete=False,
                evidenceIds=[],
                raw={"reason": "FIXTURE_MODE_IS_NOT_EXECUTION_EVIDENCE"},
            )
        try:
            if pipeline_id == "refund":
                lineage = self._aspect(REFUND_RAG_URN, "upstreamLineage") or {}
                upstreams = [
                    item.get("dataset")
                    for item in lineage.get("upstreams", [])
                    if isinstance(item, dict)
                ]
                active = next(
                    (urn for urn in upstreams if urn in {POLICY_APPROVED_URN, POLICY_DRAFT_URN}),
                    None,
                )
                properties = self._aspect(active, "datasetProperties") if active else None
                approval = self._custom_property(properties, "approvalStatus")
                return CatalogEvidenceSnapshot(
                    capturedAt=captured,
                    datahubAvailable=True,
                    approvalStatus=approval,
                    lineageComplete=active is not None,
                    evidenceIds=[item for item in [active, REFUND_RAG_URN] if item],
                    raw={"activeSourceUrn": active, "upstreams": upstreams},
                )
            if pipeline_id == "risk":
                risk_urn = (
                    "urn:li:dataset:(urn:li:dataPlatform:aegis,risk-features,PROD)"
                )
                lineage = self._aspect(risk_urn, "upstreamLineage") or {}
                complete = bool(lineage.get("upstreams"))
                operation = self._latest_operation(risk_urn)
                operation_ms = (
                    operation.get("lastUpdatedTimestamp") if operation else None
                )
                operation_at = (
                    datetime.fromtimestamp(int(operation_ms) / 1000, UTC)
                    .isoformat()
                    .replace("+00:00", "Z")
                    if operation_ms is not None
                    else None
                )
                effective_observed = operation_at
                age: int | None = None
                if effective_observed:
                    parsed = datetime.fromisoformat(effective_observed.replace("Z", "+00:00"))
                    age = max(0, int((datetime.now(UTC) - parsed).total_seconds()))
                return CatalogEvidenceSnapshot(
                    capturedAt=captured,
                    datahubAvailable=True,
                    lineageComplete=complete,
                    observedAt=effective_observed,
                    ageSeconds=age,
                    evidenceIds=[risk_urn],
                    raw={
                        "operationSource": "DataHub Operation",
                        "operation": operation,
                        "lineage": lineage,
                        "businessObservedAtIgnored": observed_at,
                    },
                )
            raise ValueError(f"Unsupported executable pipeline: {pipeline_id}")
        except (httpx.HTTPError, ValueError, TypeError) as error:
            return CatalogEvidenceSnapshot(
                capturedAt=captured,
                datahubAvailable=False,
                lineageComplete=False,
                evidenceIds=[],
                raw={"reason": type(error).__name__},
            )

    def source_system(self) -> SourceSystem:
        if (
            self.configured_mode == DataMode.LIVE_SEEDED_DATAHUB
            and self.status()["state"] == "CONNECTED"
        ):
            return SourceSystem.DATAHUB
        return SourceSystem.SEEDED_DATAHUB

    def provenance(self, *, evidence_id: str | None = None) -> Provenance:
        return Provenance(
            sourceSystem=self.source_system(),
            retrievedAt=utc_now(),
            cached=False,
            evidenceId=evidence_id,
        )

    def pipeline_records(self) -> list[dict[str, Any]]:
        return PIPELINES

    def find_pipeline(self, pipeline_id: str) -> dict[str, Any] | None:
        return next((item for item in PIPELINES if item["id"] == pipeline_id), None)

    def summaries(self, state: dict[str, Any]) -> list[PipelineSummary]:
        incident_state = IncidentState(state["incident_state"])
        items: list[PipelineSummary] = []
        for record in PIPELINES:
            trust = self._trust(record["id"], incident_state)
            change = self._change(record["id"], incident_state)
            incident = None
            if record["id"] == "refund" and incident_state not in {
                IncidentState.HEALTHY,
                IncidentState.RESOLVED,
            }:
                incident = IncidentLink(id="aegis-4821", state=incident_state)
            elif record["id"] == "risk":
                incident = IncidentLink(
                    id="aegis-7392",
                    state=IncidentState.RE_EVALUATED,
                )
            items.append(
                PipelineSummary(
                    id=record["id"],
                    name=record["name"],
                    version=record["version"],
                    environment=record["environment"],
                    trustState=trust,
                    recentChange=change,
                    highestImpactAction=record["tool"],
                    actionDetail=record["actionDetail"],
                    owner=record["owner"],
                    openIncident=incident,
                    provenance=[self.provenance(evidence_id=f"entity-{record['id']}")],
                )
            )
        order = {TrustState.BLOCKED: 0, TrustState.REVIEW: 1, TrustState.TRUSTED: 2}
        return sorted(items, key=lambda item: order[item.trustState])

    @staticmethod
    def _trust(pipeline_id: str, state: IncidentState) -> TrustState:
        if pipeline_id == "risk":
            return TrustState.REVIEW
        if pipeline_id != "refund":
            return TrustState.TRUSTED
        if state in {IncidentState.BLOCKED, IncidentState.REMEDIATION_APPLIED}:
            return TrustState.BLOCKED
        if state in {IncidentState.CONTEXT_CHANGED, IncidentState.RE_EVALUATED}:
            return TrustState.REVIEW
        return TrustState.TRUSTED

    @staticmethod
    def _change(pipeline_id: str, state: IncidentState) -> str:
        if pipeline_id == "refund":
            if state == IncidentState.HEALTHY:
                return "Approved refund-policy-v12.md is active"
            if state == IncidentState.RESOLVED:
                return "Approved refund-policy-v12.md restored and verified"
            if state in {IncidentState.REMEDIATION_APPLIED, IncidentState.RE_EVALUATED}:
                return "Approved source restored; verification pending"
            return "Unapproved refund-policy source entered context"
        if pipeline_id == "risk":
            return "Feature freshness breached review threshold"
        if pipeline_id == "support":
            return "Approved shipping knowledge is current"
        return "Procedure source verified"

    def dependencies(
        self, record: dict[str, Any], state: dict[str, Any]
    ) -> dict[str, list[Dependency]]:
        provenance = self.provenance()
        source_approved = bool(state["source_approved"]) if record["id"] == "refund" else True
        source_name = state["active_source"] if record["id"] == "refund" else record["source"]
        source_urn = (
            POLICY_APPROVED_URN
            if source_name == "refund-policy-v12.md"
            else POLICY_DRAFT_URN
            if record["id"] == "refund"
            else f"urn:li:dataset:(urn:li:dataPlatform:aegis_context,{source_name},PROD)"
        )
        return {
            "sources": [
                Dependency(
                    urn=source_urn,
                    name=source_name,
                    kind="POLICY_SOURCE",
                    status="APPROVED" if source_approved else "NOT_APPROVED",
                    version="12" if source_approved and record["id"] == "refund" else None,
                    metadata={"approvalStatus": "approved" if source_approved else "not_approved"},
                    provenance=provenance,
                )
            ],
            "retrieval": [
                Dependency(
                    urn=(
                        REFUND_RAG_URN
                        if record["id"] == "refund"
                        else f"urn:li:dataset:(urn:li:dataPlatform:aegis,{record['id']}-index,PROD)"
                    ),
                    name=record["context"],
                    kind="RETRIEVAL_INDEX",
                    status="CURRENT",
                    provenance=provenance,
                )
            ],
            "models": [
                Dependency(
                    urn=f"urn:li:mlModel:(urn:li:dataPlatform:openai,{record['id']}-model,PROD)",
                    name="Production reasoning model",
                    kind="MODEL",
                    status="PINNED",
                    provenance=provenance,
                )
            ],
            "skills": [
                Dependency(
                    urn=f"urn:li:agentSkill:{record['id']}-operations",
                    name=f"{record['name']} operations",
                    kind="SKILL",
                    status="APPROVED",
                    provenance=provenance,
                )
            ],
            "tools": [
                Dependency(
                    urn=record["toolUrn"],
                    name=record["tool"],
                    kind="TOOL",
                    status="ENFORCED",
                    metadata={"riskClass": "CONSEQUENTIAL"},
                    provenance=provenance,
                )
            ],
        }

    def graph(self, state: dict[str, Any]) -> GraphProjection:
        incident_state = IncidentState(state["incident_state"])
        active_source = state["active_source"]
        approved = bool(state["source_approved"])
        remediated = bool(state["remediation_applied"])
        source_urn = POLICY_APPROVED_URN if approved else POLICY_DRAFT_URN
        status = (
            GraphStatus.REMEDIATED
            if remediated or incident_state == IncidentState.RESOLVED
            else GraphStatus.TRUSTED
            if incident_state == IncidentState.HEALTHY
            else GraphStatus.BLOCKED
            if incident_state == IncidentState.BLOCKED
            else GraphStatus.CHANGED
        )
        source_system = self.source_system()
        nodes = [
            GraphNode(
                id="policy-source",
                urn=source_urn,
                entityType="DATASET",
                kind="POLICY_SOURCE",
                label=active_source,
                status=status,
                metadata={
                    "approvalStatus": "approved" if approved else "not_approved",
                    "owner": "Commerce Docs",
                },
                sourceSystem=source_system,
            ),
            GraphNode(
                id="refund-rag",
                urn=REFUND_RAG_URN,
                entityType="DATASET",
                kind="RETRIEVAL_INDEX",
                label="Refund RAG index",
                status=status,
                metadata={"environment": "PROD"},
                sourceSystem=source_system,
            ),
            GraphNode(
                id="refund-agent",
                urn=REFUND_AGENT_URN,
                entityType="AI_AGENT",
                kind="AGENT",
                label="Refund Resolution Agent",
                status=status,
                metadata={"version": "2.8.4"},
                sourceSystem=source_system,
            ),
            GraphNode(
                id="issue-refund",
                urn=REFUND_TOOL_URN,
                entityType="API",
                kind="TOOL",
                label="issue_refund",
                status=status,
                metadata={"riskClass": "CONSEQUENTIAL", "maximumAmount": 10000},
                sourceSystem=source_system,
            ),
        ]
        edge_status: Any = "RESTORED" if remediated else "AFFECTED" if not approved else "NORMAL"
        edges = [
            GraphEdge(
                id="policy-to-rag",
                source="policy-source",
                target="refund-rag",
                relationship=Relationship.DOWNSTREAM_OF,
                status=edge_status,
                sourceSystem=source_system,
                evidence=[EdgeEvidence(id="dh-lineage-policy-rag", label="DataHub lineage")],
            ),
            GraphEdge(
                id="rag-to-agent",
                source="refund-rag",
                target="refund-agent",
                relationship=Relationship.CONSUMES,
                status=edge_status,
                sourceSystem=source_system,
                evidence=[EdgeEvidence(id="dh-agent-consumes", label="Agent dependency")],
            ),
            GraphEdge(
                id="agent-to-tool",
                source="refund-agent",
                target="issue-refund",
                relationship=Relationship.USES_TOOL,
                status="AFFECTED" if not approved else "NORMAL",
                sourceSystem=source_system,
                evidence=[EdgeEvidence(id="dh-agent-tool", label="Agent Registry")],
            ),
        ]
        return GraphProjection(
            rootChangeUrn=source_urn,
            selectedPathNodeIds=[node.id for node in nodes],
            nodes=nodes,
            edges=edges,
            capturedAt=utc_now(),
            cached=False,
        )
