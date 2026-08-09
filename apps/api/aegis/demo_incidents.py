from dataclasses import dataclass
from typing import Any

from aegis.domain.enums import AttestationState, Decision, IncidentState, SourceSystem
from aegis.domain.models import (
    Attestation,
    AuditEvent,
    EvidenceItem,
    IncidentDetail,
    IncidentSummary,
)


@dataclass(frozen=True)
class StaticIncidentSeed:
    summary: dict[str, Any]
    owner: str
    agent_urn: str
    agent_version: str
    attestation_state: AttestationState
    evidence: list[dict[str, Any]]
    audit_events: list[dict[str, Any]]
    writeback_state: str


STATIC_INCIDENT_SEEDS = (
    StaticIncidentSeed(
        summary={
            "id": "aegis-7392",
            "pipelineId": "risk",
            "pipelineName": "Account Risk Agent",
            "environment": "PRODUCTION",
            "state": IncidentState.RE_EVALUATED,
            "decision": Decision.REVIEW,
            "causalChange": "risk_features_daily missed its freshness SLA",
            "preventedAction": "freeze_account held for analyst approval",
            "recommendedNextStep": "Confirm the refreshed feature operation, then re-attest",
            "openedAt": "2026-08-08T13:42:18Z",
            "resolvedAt": None,
            "version": 3,
        },
        owner="Trust Operations",
        agent_urn="urn:li:aiAgent:account-risk-agent-v3_1_0",
        agent_version="3.1.0",
        attestation_state=AttestationState.RE_EVALUATED,
        evidence=[
            {
                "label": "Freshness assertion",
                "value": "Observed 23m old · SLA 15m",
                "detail": (
                    "The latest feature materialization exceeded the production "
                    "freshness threshold."
                ),
                "sourceSystem": SourceSystem.SEEDED_DATAHUB,
                "raw": {"observedAgeSeconds": 1380, "slaSeconds": 900},
            },
            {
                "label": "Governed tool proposal",
                "value": "freeze_account({ accountId: 'ACC-HIGH-7' })",
                "detail": (
                    "Aegis routed the restriction request to human review instead "
                    "of the executor."
                ),
                "sourceSystem": SourceSystem.AEGIS,
                "raw": {"tool": "freeze_account", "executed": False},
            },
            {
                "label": "Owner acknowledgement",
                "value": "Trust Operations acknowledged at 14:01 UTC",
                "detail": "A refreshed feature operation is present and awaits final attestation.",
                "sourceSystem": SourceSystem.SEEDED_DATAHUB,
                "raw": {"owner": "Trust Operations", "status": "ACKNOWLEDGED"},
            },
        ],
        audit_events=[
            {
                "type": "CONTEXT_RE_EVALUATED",
                "actor": "aegis-risk-monitor",
                "occurredAt": "2026-08-08T14:08:44Z",
                "detail": "Refreshed feature operation captured; human review remains required.",
                "sourceSystem": SourceSystem.AEGIS,
            },
            {
                "type": "TOOL_CALL_HELD",
                "actor": "account-risk-agent-v3.1.0",
                "occurredAt": "2026-08-08T13:42:18Z",
                "detail": (
                    "freeze_account was held before execution because risk features "
                    "were stale."
                ),
                "sourceSystem": SourceSystem.AEGIS,
            },
        ],
        writeback_state="ACTIVE",
    ),
    StaticIncidentSeed(
        summary={
            "id": "aegis-6158",
            "pipelineId": "support",
            "pipelineName": "Customer Support Agent",
            "environment": "PRODUCTION",
            "state": IncidentState.RESOLVED,
            "decision": Decision.ALLOW,
            "causalChange": "Shipping knowledge owner metadata was removed",
            "preventedAction": "escalate_case paused until ownership was restored",
            "recommendedNextStep": "No action · resolution evidence retained",
            "openedAt": "2026-08-07T16:18:09Z",
            "resolvedAt": "2026-08-07T16:46:31Z",
            "version": 5,
        },
        owner="CX Automation",
        agent_urn="urn:li:aiAgent:customer-support-agent-v4_6_2",
        agent_version="4.6.2",
        attestation_state=AttestationState.TRUSTED,
        evidence=[
            {
                "label": "Ownership control",
                "value": "CX Knowledge Systems · restored",
                "detail": (
                    "The approved owner was restored on the active shipping "
                    "knowledge dataset."
                ),
                "sourceSystem": SourceSystem.SEEDED_DATAHUB,
                "raw": {"owner": "CX Knowledge Systems", "verified": True},
            },
            {
                "label": "Prevented escalation",
                "value": "escalate_case({ caseId: 'CASE-7719' })",
                "detail": (
                    "The escalation remained paused while required ownership "
                    "evidence was absent."
                ),
                "sourceSystem": SourceSystem.AEGIS,
                "raw": {"tool": "escalate_case", "executed": False},
            },
            {
                "label": "Closure verification",
                "value": "Support context regression · 12/12 passed",
                "detail": (
                    "Ownership, retrieval, and escalation policy checks passed "
                    "after remediation."
                ),
                "sourceSystem": SourceSystem.AEGIS,
                "raw": {"suite": "support-context-v2", "passed": 12, "total": 12},
            },
        ],
        audit_events=[
            {
                "type": "INCIDENT_RESOLVED",
                "actor": "aegis-demo-operator",
                "occurredAt": "2026-08-07T16:46:31Z",
                "detail": (
                    "Ownership metadata and the trusted support attestation were "
                    "written back."
                ),
                "sourceSystem": SourceSystem.AEGIS,
            },
            {
                "type": "REQUIRED_OWNER_MISSING",
                "actor": "support-context-monitor",
                "occurredAt": "2026-08-07T16:18:09Z",
                "detail": "The active shipping knowledge dataset had no approved owner.",
                "sourceSystem": SourceSystem.SEEDED_DATAHUB,
            },
        ],
        writeback_state="RESOLVED",
    ),
    StaticIncidentSeed(
        summary={
            "id": "aegis-4770",
            "pipelineId": "claims",
            "pipelineName": "Claims Triage Agent",
            "environment": "PRODUCTION",
            "state": IncidentState.RESOLVED,
            "decision": Decision.ALLOW,
            "causalChange": "claims-procedure-v7 re-entered the retrieval index",
            "preventedAction": "route_claim paused on the superseded procedure",
            "recommendedNextStep": "No action · monitor nightly regression",
            "openedAt": "2026-08-05T09:11:52Z",
            "resolvedAt": "2026-08-05T10:03:27Z",
            "version": 4,
        },
        owner="Claims Platform",
        agent_urn="urn:li:aiAgent:claims-triage-agent-v1_9_7",
        agent_version="1.9.7",
        attestation_state=AttestationState.TRUSTED,
        evidence=[
            {
                "label": "Superseded procedure",
                "value": "claims-procedure-v7.md · inactive",
                "detail": (
                    "DataHub lineage showed the retired procedure alongside the "
                    "approved v8 source."
                ),
                "sourceSystem": SourceSystem.SEEDED_DATAHUB,
                "raw": {"version": 7, "lifecycle": "DEPRECATED"},
            },
            {
                "label": "Routing safeguard",
                "value": "route_claim held for 51 minutes",
                "detail": (
                    "Claim assignment resumed only after the retrieval index was "
                    "rebuilt from v8."
                ),
                "sourceSystem": SourceSystem.AEGIS,
                "raw": {"tool": "route_claim", "executed": False, "holdMinutes": 51},
            },
            {
                "label": "Verified replacement",
                "value": "claims-procedure-v8.md · approved",
                "detail": "The active lineage now contains only the approved procedure version.",
                "sourceSystem": SourceSystem.SEEDED_DATAHUB,
                "raw": {"version": 8, "approvalStatus": "approved"},
            },
        ],
        audit_events=[
            {
                "type": "INCIDENT_RESOLVED",
                "actor": "claims-platform-oncall",
                "occurredAt": "2026-08-05T10:03:27Z",
                "detail": "The v8-only index passed routing regressions and was re-attested.",
                "sourceSystem": SourceSystem.AEGIS,
            },
            {
                "type": "SUPERSEDED_CONTEXT_DETECTED",
                "actor": "claims-context-monitor",
                "occurredAt": "2026-08-05T09:11:52Z",
                "detail": (
                    "A retired claims procedure was detected in the production "
                    "retrieval path."
                ),
                "sourceSystem": SourceSystem.SEEDED_DATAHUB,
            },
        ],
        writeback_state="RESOLVED",
    ),
)


def static_incident_details() -> dict[str, IncidentDetail]:
    details: dict[str, IncidentDetail] = {}
    for seed in STATIC_INCIDENT_SEEDS:
        summary = IncidentSummary.model_validate(seed.summary)
        evidence_timestamp = summary.resolvedAt or summary.openedAt
        details[summary.id] = IncidentDetail(
            incident=summary,
            attestation=Attestation(
                id=f"att-{summary.pipelineId}-{summary.id}",
                agentUrn=seed.agent_urn,
                agentVersion=seed.agent_version,
                environment=summary.environment,
                owner=seed.owner,
                state=seed.attestation_state,
                decision=summary.decision,
                graphFingerprint=f"sha256:static-{summary.id}",
                evidenceTimestamp=evidence_timestamp,
                incidentId=summary.id,
                remediationState=(
                    "VERIFIED" if summary.state == IncidentState.RESOLVED else "APPLIED"
                ),
            ),
            availableActions=[],
            evidenceSummary=[
                EvidenceItem(id=f"{summary.id}-evidence-{index}", **item)
                for index, item in enumerate(seed.evidence, start=1)
            ],
            auditEvents=[
                AuditEvent(id=f"{summary.id}-event-{index}", **item)
                for index, item in enumerate(seed.audit_events, start=1)
            ],
            datahubIncidentUrn=f"urn:li:incident:{summary.id}",
            writeBackState=seed.writeback_state,
        )
    return details


STATIC_INCIDENT_DETAILS = static_incident_details()
