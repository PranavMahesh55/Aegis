import asyncio
import hashlib
import hmac
import json
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import StreamingResponse

from aegis.adapters.datahub.client import DataHubAdapter
from aegis.demo_incidents import STATIC_INCIDENT_DETAILS
from aegis.domain.enums import AttestationState, Decision, RunStatus, TrustState
from aegis.domain.models import (
    AgentRun,
    AgentRunAccepted,
    AgentRunRequest,
    Attestation,
    ContextChangeRequest,
    ControlDefinition,
    ControlEvaluation,
    Dependency,
    EvaluateRequest,
    PipelineDetail,
    RemediateRequest,
    ResetRequest,
    RuntimeToolRequest,
    SystemStatus,
    VerifyRequest,
)
from aegis.persistence.store import AegisStore, utc_now
from aegis.services.agent_runtime import AgentRunService
from aegis.services.workflow import WorkflowService

router = APIRouter(prefix="/api")


def services(request: Request) -> tuple[AegisStore, DataHubAdapter, WorkflowService]:
    return request.app.state.store, request.app.state.datahub, request.app.state.workflow


def run_service(request: Request) -> AgentRunService:
    return request.app.state.agent_runs


def datahub_entity_url(frontend_url: str, path_name: str, urn: str) -> str:
    """Build the entity URL using DataHub's React Router URN encoding rules."""
    encoded = (
        urn.replace("%", "{{encoded_percent}}")
        .replace("/", "%2F")
        .replace("?", "%3F")
        .replace("#", "%23")
        .replace("[", "%5B")
        .replace("]", "%5D")
    )
    return f"{frontend_url.rstrip('/')}/{path_name}/{encoded}"


@router.get("/health/live")
def health_live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/system/status", response_model=SystemStatus)
def system_status(request: Request) -> SystemStatus:
    store, datahub, _ = services(request)
    state = store.get_state()
    datahub_status = datahub.status()
    return SystemStatus(
        api="HEALTHY" if datahub_status["state"] != "DEGRADED" else "DEGRADED",
        frontend="AVAILABLE",
        datahub=datahub_status,
        dataMode=datahub.configured_mode,
        seedVersion="aegis-demo-v1",
        projection={"cached": False, "capturedAt": state["updated_at"]},
    )


@router.get("/pipelines")
def list_pipelines(request: Request) -> dict[str, Any]:
    store, datahub, _ = services(request)
    return {
        "items": datahub.summaries(store.get_state()),
        "asOf": utc_now(),
        "cached": False,
        "dataMode": datahub.configured_mode,
    }


@router.get("/pipelines/{pipeline_id}", response_model=PipelineDetail)
def get_pipeline(pipeline_id: str, request: Request) -> PipelineDetail:
    store, datahub, workflow = services(request)
    state = store.get_state()
    record = datahub.find_pipeline(pipeline_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    summary = next(item for item in datahub.summaries(state) if item.id == pipeline_id)
    datahub_connected = datahub.status()["state"] == "CONNECTED"
    provenance = datahub.provenance(evidence_id=f"agent-{pipeline_id}")
    dependencies = datahub.dependencies(record, state)
    # DataHub Core 1.7 accepts Agent Registry metadata through GMS but does not
    # ship the Cloud Agent Registry profile UI. Link to the pipeline's governed,
    # browseable context asset so the local Core button always opens a real page.
    context_asset = next(iter(dependencies.get("retrieval", [])), None)
    agent = Dependency(
        urn=record["agentUrn"],
        name=record["name"],
        kind="AI_AGENT",
        status=summary.trustState.value,
        version=record["version"],
        metadata={"environment": record["environment"], "owner": record["owner"]},
        provenance=provenance,
    )
    if pipeline_id == "refund":
        attestation = workflow.attestation()
    else:
        attestation = Attestation(
            id=f"att-{pipeline_id}-{record['version']}",
            agentUrn=record["agentUrn"],
            agentVersion=record["version"],
            environment=record["environment"],
            owner=record["owner"],
            state=(
                AttestationState.RE_EVALUATED if pipeline_id == "risk" else AttestationState.TRUSTED
            ),
            decision=Decision.REVIEW if pipeline_id == "risk" else Decision.ALLOW,
            graphFingerprint=f"sha256:seeded-{pipeline_id}",
            evidenceTimestamp=state["updated_at"],
        )
    return PipelineDetail(
        pipeline=summary,
        agent=agent,
        attestation=attestation,
        dependencies=dependencies,
        highestImpactPermission={
            "toolUrn": record["toolUrn"],
            "tool": record["tool"],
            "riskClass": "CONSEQUENTIAL",
            "detail": record["actionDetail"],
        },
        recentChanges=record["recent"],
        openIncident=summary.openIncident,
        factGroups={"datahubSupplied": record["datahub"], "aegisProduced": record["aegis"]},
        executionCapability=("EXECUTABLE" if pipeline_id in {"refund", "risk"} else "CATALOG_ONLY"),
        runtimeStatus=(
            "MODEL_NOT_CONFIGURED"
            if not run_service(request).settings.openai_api_key
            else "READY"
            if run_service(request).settings.data_mode.lower() == "live" and datahub_connected
            else "DATAHUB_UNAVAILABLE"
            if run_service(request).settings.data_mode.lower() == "live"
            else "FIXTURE_ONLY"
        ),
        model=(
            run_service(request).settings.openai_model
            if pipeline_id in {"refund", "risk"}
            else None
        ),
        skills=(
            ["DataHub governance", "Business context", record["tool"]]
            if pipeline_id in {"refund", "risk"}
            else []
        ),
        datahubUrl=(
            datahub_entity_url(
                run_service(request).settings.datahub_frontend_url,
                "dataset",
                context_asset.urn,
            )
            if context_asset
            else None
        ),
        latestRun=store.latest_run(pipeline_id),
    )


@router.post("/agents/{pipeline_id}/runs", response_model=AgentRunAccepted, status_code=202)
async def create_agent_run(
    pipeline_id: str, body: AgentRunRequest, request: Request
) -> AgentRunAccepted:
    service = run_service(request)
    run = service.admit(pipeline_id, body)
    service.start(run)
    return AgentRunAccepted(
        runId=run.id,
        status=run.status,
        streamUrl=f"/api/runs/{run.id}/events",
    )


@router.get("/runs/{run_id}", response_model=AgentRun)
def get_agent_run(run_id: str, request: Request) -> AgentRun:
    run = services(request)[0].get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Agent run not found")
    return run


@router.get("/runs/{run_id}/events")
async def stream_agent_run(run_id: str, request: Request) -> StreamingResponse:
    store = services(request)[0]
    if store.get_run(run_id, include_steps=False) is None:
        raise HTTPException(status_code=404, detail="Agent run not found")

    async def events() -> Any:
        sequence = 0
        while True:
            if await request.is_disconnected():
                return
            for step in store.list_run_steps(run_id, after_sequence=sequence):
                sequence = step.sequence
                yield (
                    f"id: {step.sequence}\nevent: run_step\n" f"data: {step.model_dump_json()}\n\n"
                )
            run = store.get_run(run_id, include_steps=False)
            if run and run.status in {
                RunStatus.COMPLETED,
                RunStatus.FAILED,
                RunStatus.BLOCKED,
                RunStatus.REVIEW,
            }:
                yield f"event: complete\ndata: {run.model_dump_json()}\n\n"
                return
            await asyncio.sleep(0.25)

    return StreamingResponse(events(), media_type="text/event-stream")


@router.post("/integrations/datahub/events", status_code=202)
async def receive_datahub_event(request: Request) -> Response:
    body = await request.body()
    settings = run_service(request).settings
    supplied = request.headers.get("x-aegis-signature", "")
    expected = (
        "sha256="
        + hmac.new(
            settings.datahub_actions_shared_secret.encode(), body, hashlib.sha256
        ).hexdigest()
    )
    if not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="Invalid DataHub Actions signature")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=400, detail="Invalid JSON event") from error
    event_id = request.headers.get("x-datahub-event-id") or hashlib.sha256(body).hexdigest()
    event_payload = payload.get("event", payload)
    entity_urn = str(event_payload.get("entityUrn") or event_payload.get("entity_urn") or "unknown")
    event_type = str(payload.get("eventType") or payload.get("event_type") or "MCL")
    inserted = services(request)[0].receive_datahub_event(event_id, event_type, entity_urn, payload)
    if inserted:
        store, _, workflow = services(request)
        store.append_audit(
            "DATAHUB_CHANGE_EVENT_RECEIVED",
            f"DataHub Actions reported {event_type} for {entity_urn}",
            payload={"eventId": event_id},
        )
        workflow.ingest_datahub_change(entity_urn)
    return Response(status_code=202, headers={"X-Aegis-Event-Accepted": str(inserted).lower()})


@router.get("/incidents")
def list_incidents(request: Request, state: str | None = None) -> dict[str, Any]:
    _, _, workflow = services(request)
    items = [workflow.incident_summary()] + [
        detail.incident for detail in STATIC_INCIDENT_DETAILS.values()
    ]
    if state is not None:
        items = [item for item in items if item.state.value == state.upper()]
    return {"items": items, "total": len(items)}


@router.get("/incidents/{incident_id}")
def get_incident(incident_id: str, request: Request) -> Any:
    if incident_id == "aegis-4821":
        _, _, workflow = services(request)
        return workflow.detail()
    detail = STATIC_INCIDENT_DETAILS.get(incident_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return detail


@router.get("/incidents/{incident_id}/graph")
def get_incident_graph(incident_id: str, request: Request) -> Any:
    if incident_id != "aegis-4821":
        raise HTTPException(status_code=404, detail="Incident not found")
    store, datahub, _ = services(request)
    return datahub.graph(store.get_state())


@router.post("/demo/context-change")
def simulate_context_change(body: ContextChangeRequest, request: Request) -> Any:
    _, _, workflow = services(request)
    return workflow.context_change(body.expectedIncidentVersion)


@router.post("/incidents/{incident_id}/evaluate")
def evaluate_incident(incident_id: str, body: EvaluateRequest, request: Request) -> Any:
    if incident_id != "aegis-4821":
        raise HTTPException(status_code=404, detail="Incident not found")
    _, _, workflow = services(request)
    return workflow.evaluate(body.expectedVersion, body.toolCall)


@router.post("/incidents/{incident_id}/remediate")
def remediate_incident(incident_id: str, body: RemediateRequest, request: Request) -> Any:
    if incident_id != "aegis-4821":
        raise HTTPException(status_code=404, detail="Incident not found")
    _, _, workflow = services(request)
    return workflow.remediate(body.expectedVersion)


@router.post("/incidents/{incident_id}/verify")
def verify_incident(incident_id: str, body: VerifyRequest, request: Request) -> Any:
    if incident_id != "aegis-4821":
        raise HTTPException(status_code=404, detail="Incident not found")
    _, _, workflow = services(request)
    return workflow.verify(body.expectedVersion, body.suiteId)


@router.post("/demo/reset")
def reset_demo(body: ResetRequest, request: Request) -> dict[str, Any]:
    store, datahub, _ = services(request)
    state = store.reset(blocked=False)
    request.app.state.context_store.reset()
    datahub_change = datahub.switch_refund_context(poisoned=False)
    return {
        "state": state["incident_state"],
        "pipelineTrustState": TrustState.TRUSTED,
        "incidentState": "DORMANT",
        "seedVersion": "aegis-demo-v1",
        "datahubVerified": datahub.status()["state"] == "CONNECTED",
        "dataMode": datahub.configured_mode,
        "datahubChange": datahub_change,
    }


@router.post("/demo/prime")
def prime_demo(request: Request) -> dict[str, Any]:
    store, datahub, _ = services(request)
    state = store.reset(blocked=True)
    request.app.state.context_store.reset()
    request.app.state.context_store.activate_refund_policy(poisoned=True)
    datahub_change = datahub.switch_refund_context(poisoned=True)
    return {
        "state": state["incident_state"],
        "pipelineTrustState": TrustState.BLOCKED,
        "incidentState": "ACTIVE",
        "seedVersion": "aegis-demo-v1",
        "datahubVerified": datahub.status()["state"] == "CONNECTED",
        "dataMode": datahub.configured_mode,
        "datahubChange": datahub_change,
    }


@router.get("/controls")
def get_controls(request: Request) -> dict[str, Any]:
    store, _, _ = services(request)
    latest = store.latest_json("evaluations")
    approved_context = ControlDefinition(
        id="approved-context-source",
        name="ApprovedContextSource",
        version="1",
        enabled=True,
        scope={"environment": "PRODUCTION", "tool": "issue_refund"},
        conditions=[
            {"field": "amount", "operator": "GREATER_THAN", "value": 2000},
            {"field": "context.approvalStatus", "operator": "EQUALS", "value": "approved"},
            {"field": "lineage.complete", "operator": "EQUALS", "value": True},
        ],
        missingEvidencePolicy="BLOCK",
        lastEvaluation=ControlEvaluation.model_validate(latest) if latest else None,
        coveredAgents=["refund"],
        linkedIncidentId="aegis-4821",
    )
    fresh_risk = ControlDefinition(
        id="fresh-risk-context",
        name="FreshRiskContext",
        version="1",
        enabled=True,
        scope={"environment": "PRODUCTION", "tool": "freeze_account"},
        conditions=[
            {"field": "risk.ageSeconds", "operator": "LESS_THAN_OR_EQUAL", "value": 900},
            {"field": "lineage.complete", "operator": "EQUALS", "value": True},
            {"field": "datahub.available", "operator": "EQUALS", "value": True},
        ],
        missingEvidencePolicy="BLOCK",
        lastEvaluation=ControlEvaluation(
            id="eval-risk-aegis-7392",
            controlId="fresh-risk-context",
            decision=Decision.REVIEW,
            reasonCode="STALE_RISK_CONTEXT",
            conditionResults=[
                {
                    "field": "environment",
                    "operator": "EQUALS",
                    "expected": "PRODUCTION",
                    "actual": "PRODUCTION",
                    "passed": True,
                    "evidenceId": "risk-environment",
                },
                {
                    "field": "tool",
                    "operator": "EQUALS",
                    "expected": "freeze_account",
                    "actual": "freeze_account",
                    "passed": True,
                    "evidenceId": "risk-tool",
                },
                {
                    "field": "risk.ageSeconds",
                    "operator": "LESS_THAN_OR_EQUAL",
                    "expected": 900,
                    "actual": 1380,
                    "passed": False,
                    "evidenceId": "risk-operation-freshness",
                },
                {
                    "field": "lineage.complete",
                    "operator": "EQUALS",
                    "expected": True,
                    "actual": True,
                    "passed": True,
                    "evidenceId": "risk-lineage",
                },
                {
                    "field": "datahub.available",
                    "operator": "EQUALS",
                    "expected": True,
                    "actual": True,
                    "passed": True,
                    "evidenceId": "risk-datahub",
                },
            ],
            evidenceIds=[
                "risk-environment",
                "risk-tool",
                "risk-operation-freshness",
                "risk-lineage",
                "risk-datahub",
            ],
            evaluatedAt="2026-08-08T14:08:44Z",
        ),
        coveredAgents=["risk"],
        linkedIncidentId="aegis-7392",
    )
    return {"items": [approved_context, fresh_risk]}


@router.post("/demo/tools/issue_refund")
def runtime_issue_refund(body: RuntimeToolRequest, request: Request) -> dict[str, Any]:
    store, datahub, workflow = services(request)
    state = store.get_state()
    datahub_available = datahub.status()["state"] in {"CONNECTED", "SEEDED_OFFLINE"}
    evaluation, receipt = workflow.gateway.intercept(
        body.toolCall,
        approval_status="approved" if state["source_approved"] else "not_approved",
        lineage_complete=True,
        datahub_available=datahub_available,
    )
    store.append_audit(
        "RUNTIME_TOOL_DECISION",
        f"Runtime gateway returned {evaluation.decision.value} for issue_refund",
        payload={"evaluationId": evaluation.id, "executed": receipt is not None},
    )
    return {
        "decision": evaluation.decision,
        "executed": receipt is not None,
        "reasonCode": evaluation.reasonCode,
        "evaluationId": evaluation.id,
        "evidenceIds": evaluation.evidenceIds,
        "simulatedReceipt": receipt,
    }
