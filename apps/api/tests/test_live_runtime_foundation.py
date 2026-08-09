import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aegis.adapters.datahub.client import DataHubAdapter
from aegis.config import Settings
from aegis.context_store import BusinessContextStore
from aegis.controls.fresh_risk_context import FreshRiskContext, RiskEvaluationInput
from aegis.domain.enums import Decision, RunStatus, RunStepType, SourceSystem
from aegis.domain.models import (
    AgentRun,
    CatalogEvidenceSnapshot,
    GateDecision,
    RunStep,
    RunSubject,
)
from aegis.persistence.store import AegisStore, utc_now
from aegis.security.capabilities import (
    InvalidCapability,
    mint_capability,
    verify_capability,
)
from aegis.services.agent_runtime import AgentRunService, AgentRuntime


def test_capability_is_bound_to_exact_tool_arguments() -> None:
    secret = "a-test-secret-long-enough"
    arguments = {"caseId": "CASE-1042", "amount": 1500.0, "currency": "USD"}
    token = mint_capability(
        secret, tool="issue_refund", arguments=arguments, run_id="run-1"
    )
    payload = verify_capability(
        secret, token, tool="issue_refund", arguments=arguments
    )
    assert payload["decision"] == "ALLOW"
    # JSON decoders and typed MCP parameters may represent the same number as
    # int and float on opposite sides of the capability boundary.
    verify_capability(
        secret,
        token,
        tool="issue_refund",
        arguments={**arguments, "amount": 1500},
    )
    with pytest.raises(InvalidCapability, match="arguments do not match"):
        verify_capability(
            secret,
            token,
            tool="issue_refund",
            arguments={**arguments, "amount": 8500.0},
        )
    with pytest.raises(InvalidCapability, match="signature"):
        verify_capability(secret + "tampered", token, tool="issue_refund", arguments=arguments)


def test_business_executor_consumes_capability_only_once(tmp_path: Path) -> None:
    store = BusinessContextStore(tmp_path / "context.db")
    receipt = store.record_consequence(
        tool="issue_refund",
        subject_id="CASE-1042",
        arguments={"amount": 1500},
        run_id="run-1",
        capability_id="cap-1",
    )
    assert receipt["status"] == "SIMULATED_ACCEPTED"
    with pytest.raises(ValueError, match="already been consumed"):
        store.record_consequence(
            tool="issue_refund",
            subject_id="CASE-1042",
            arguments={"amount": 1500},
            run_id="run-1",
            capability_id="cap-1",
        )


def risk_input(**overrides: object) -> RiskEvaluationInput:
    values = {
        "environment": "PRODUCTION",
        "tool": "freeze_account",
        "observed_at": datetime.now(UTC).isoformat(),
        "freshness_sla_seconds": 900,
        "lineage_complete": True,
        "datahub_available": True,
    }
    values.update(overrides)
    return RiskEvaluationInput(**values)  # type: ignore[arg-type]


def test_risk_control_reviews_stale_but_blocks_missing_evidence() -> None:
    control = FreshRiskContext()
    stale = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    assert control.evaluate(risk_input(observed_at=stale)).decision == Decision.REVIEW
    assert (
        control.evaluate(risk_input(observed_at=None)).reason_code
        == "MISSING_RISK_OPERATION"
    )
    assert (
        control.evaluate(risk_input(datahub_available=False)).decision == Decision.BLOCK
    )


def test_agent_run_and_steps_round_trip(tmp_path: Path) -> None:
    store = AegisStore(tmp_path / "state.db", prime_blocked=False)
    timestamp = utc_now()
    run = AgentRun(
        id="run-test",
        pipelineId="refund",
        status=RunStatus.RUNNING,
        message="refund it",
        subject=RunSubject(type="CASE", id="CASE-1042"),
        model="gpt-test",
        startedAt=timestamp,
        updatedAt=timestamp,
    )
    store.save_run(run)
    store.append_run_step(
        RunStep(
            id="step-test",
            runId=run.id,
            sequence=1,
            type=RunStepType.RUN_STARTED,
            title="Started",
            detail="test",
            sourceSystem=SourceSystem.AEGIS,
            occurredAt=timestamp,
        )
    )
    restored = store.get_run(run.id)
    assert restored is not None
    assert restored.status == RunStatus.RUNNING
    assert [step.sequence for step in restored.steps] == [1]


def test_model_tool_proposal_is_bound_to_subject_and_business_facts() -> None:
    timestamp = utc_now()
    run = AgentRun(
        id="run-binding",
        pipelineId="refund",
        status=RunStatus.RUNNING,
        message="refund it",
        subject=RunSubject(type="CASE", id="CASE-1042"),
        model="gpt-test",
        startedAt=timestamp,
        updatedAt=timestamp,
    )
    context = {
        "case": {"id": "CASE-1042", "order_total": 1500.0, "currency": "USD"}
    }
    valid = {
        "tool": "issue_refund",
        "arguments": {"caseId": "CASE-1042", "amount": 1500.0, "currency": "USD"},
    }
    assert AgentRuntime._proposal_binding_error(run, valid, context) is None
    assert (
        AgentRuntime._proposal_binding_error(
            run, {**valid, "arguments": {**valid["arguments"], "caseId": "CASE-8500"}}, context
        )
        == "SUBJECT_BINDING_FAILED"
    )
    assert (
        AgentRuntime._proposal_binding_error(
            run, {**valid, "arguments": {**valid["arguments"], "amount": 8500.0}}, context
        )
        == "BUSINESS_FACT_BINDING_FAILED"
    )


def security_run(status: RunStatus, decision: Decision) -> AgentRun:
    timestamp = utc_now()
    return AgentRun(
        id=f"run-{status.value.lower()}",
        pipelineId="refund",
        status=status,
        message="refund it",
        subject=RunSubject(type="CASE", id="CASE-1042"),
        model="gpt-test",
        startedAt=timestamp,
        updatedAt=timestamp,
        completedAt=timestamp,
        proposedToolCall={
            "tool": "issue_refund",
            "arguments": {"caseId": "CASE-1042", "amount": 1500, "currency": "USD"},
        },
        gateDecision=GateDecision(
            decision=decision,
            reasonCode=(
                "CONTEXT_SOURCE_APPROVED"
                if decision == Decision.ALLOW
                else "SOURCE_NOT_APPROVED"
            ),
            controlId="approved-context-source",
            evidenceSnapshot=CatalogEvidenceSnapshot(
                capturedAt=timestamp,
                datahubAvailable=True,
                approvalStatus="APPROVED" if decision == Decision.ALLOW else "DRAFT",
                lineageComplete=True,
                evidenceIds=["urn:li:dataset:refund-rag-index"],
            ),
        ),
        toolReceipt={"id": "receipt-1"} if decision == Decision.ALLOW else None,
    )


def test_run_outcome_publishes_attestation_or_incident(tmp_path: Path) -> None:
    class RecordingDataHub:
        def write_run_attestation_document(self, run: AgentRun) -> str:
            return f"urn:li:document:aegis-run-attestation-{run.id}"

        def write_run_incident(self, run: AgentRun) -> str:
            return f"urn:li:incident:aegis-{run.id}"

    service = AgentRunService(
        Settings(data_mode="live"),
        AegisStore(tmp_path / "writeback.db", prime_blocked=False),
        RecordingDataHub(),  # type: ignore[arg-type]
    )
    allowed = service._publish_run_outcome(security_run(RunStatus.COMPLETED, Decision.ALLOW))
    blocked = service._publish_run_outcome(security_run(RunStatus.BLOCKED, Decision.BLOCK))

    assert allowed.status == "WRITTEN"
    assert allowed.recordType == "ATTESTATION"
    assert allowed.urn == "urn:li:document:aegis-run-attestation-run-completed"
    assert blocked.status == "WRITTEN"
    assert blocked.recordType == "INCIDENT"
    assert blocked.urn == "urn:li:incident:aegis-run-blocked"


def test_run_writeback_failure_is_visible_without_changing_run_decision(tmp_path: Path) -> None:
    class UnavailableDataHub:
        def write_run_attestation_document(self, run: AgentRun) -> str:
            raise RuntimeError("GMS unavailable")

        def write_run_incident(self, run: AgentRun) -> str:
            raise RuntimeError("GMS unavailable")

    service = AgentRunService(
        Settings(data_mode="live"),
        AegisStore(tmp_path / "failed-writeback.db", prime_blocked=False),
        UnavailableDataHub(),  # type: ignore[arg-type]
    )
    run = security_run(RunStatus.BLOCKED, Decision.BLOCK)
    writeback = service._publish_run_outcome(run)

    assert run.status == RunStatus.BLOCKED
    assert run.gateDecision is not None and run.gateDecision.decision == Decision.BLOCK
    assert writeback.status == "FAILED"
    assert writeback.recordType == "INCIDENT"
    assert "GMS unavailable" in writeback.detail


def test_datahub_run_incident_contains_run_level_security_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = DataHubAdapter(Settings(data_mode="live"))
    captured: dict[str, object] = {}

    def capture(**kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(adapter, "_emit_aspect", capture)
    urn = adapter.write_run_incident(security_run(RunStatus.BLOCKED, Decision.BLOCK))

    assert urn == "urn:li:incident:aegis-run-blocked"
    assert captured["entity_type"] == "incident"
    aspect = captured["aspect"]
    assert isinstance(aspect, dict)
    assert aspect["customType"] == "AEGIS_AGENT_RUN_SECURITY"
    assert "run-blocked" in aspect["description"]
    assert "SOURCE_NOT_APPROVED" in aspect["description"]
    assert "issue_refund" in aspect["description"]
    assert aspect["entities"] == [
        "urn:li:aiAgent:refund-resolution-agent-v2_8_4",
        "urn:li:dataset:(urn:li:dataPlatform:pinecone,refund-rag-index,PROD)",
    ]


def test_run_admission_and_actions_authentication(client: TestClient) -> None:
    catalog_only = client.post(
        "/api/agents/support/runs",
        json={"message": "help", "subject": {"type": "CASE", "id": "CASE-1"}},
    )
    assert catalog_only.status_code == 409
    assert catalog_only.json()["code"] == "AGENT_NOT_EXECUTABLE"

    missing_model = client.post(
        "/api/agents/refund/runs",
        json={"message": "refund", "subject": {"type": "CASE", "id": "CASE-1042"}},
    )
    assert missing_model.status_code == 503
    assert missing_model.json()["code"] == "MODEL_NOT_CONFIGURED"

    event = {
        "event_type": "MetadataChangeLogEvent_v1",
        "event": {"entityUrn": "urn:li:dataset:refund-rag-index"},
    }
    body = json.dumps(event, sort_keys=True, separators=(",", ":")).encode()
    rejected = client.post("/api/integrations/datahub/events", content=body)
    assert rejected.status_code == 401
    signature = hmac.new(b"dev-actions-change-me", body, hashlib.sha256).hexdigest()
    accepted = client.post(
        "/api/integrations/datahub/events",
        content=body,
        headers={"X-Aegis-Signature": f"sha256={signature}"},
    )
    assert accepted.status_code == 202
    assert accepted.headers["X-Aegis-Event-Accepted"] == "true"
    duplicate = client.post(
        "/api/integrations/datahub/events",
        content=body,
        headers={"X-Aegis-Signature": f"sha256={signature}"},
    )
    assert duplicate.headers["X-Aegis-Event-Accepted"] == "false"
