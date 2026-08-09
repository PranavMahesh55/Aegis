import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any, TypedDict
from uuid import uuid4

from aegis.adapters.datahub.client import DataHubAdapter
from aegis.adapters.datahub.seed import REFUND_RAG_URN, RISK_FEATURES_URN
from aegis.config import Settings
from aegis.controls.approved_context_source import EvaluationInput
from aegis.controls.fresh_risk_context import RiskEvaluationInput
from aegis.domain.enums import Decision, RunStatus, RunStepType, SourceSystem
from aegis.domain.models import (
    AgentRun,
    AgentRunRequest,
    CatalogEvidenceSnapshot,
    DataHubRunWriteback,
    GateDecision,
    RunStep,
)
from aegis.persistence.store import AegisStore, utc_now
from aegis.security.capabilities import mint_capability
from aegis.services.mcp_client import call_mcp_tool
from aegis.services.safety_engine import SafetyEngine

EXECUTABLE_PIPELINES = {"refund", "risk"}


class RunAdmissionError(RuntimeError):
    def __init__(self, status_code: int, code: str, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.code = code
        self.detail = detail


class AgentState(TypedDict, total=False):
    run: AgentRun
    governance_context: Any
    business_context: Any
    evidence: CatalogEvidenceSnapshot
    proposal: dict[str, Any]
    decision: GateDecision
    receipt: dict[str, Any] | None
    output: str


StepEmitter = Callable[[RunStepType, str, str, SourceSystem, dict[str, Any]], Awaitable[None]]


class AgentRuntime:
    """Two real LangGraph workflows with model-generated consequential tool proposals."""

    def __init__(self, settings: Settings, store: AegisStore, datahub: DataHubAdapter) -> None:
        self.settings = settings
        self.store = store
        self.datahub = datahub
        self.safety = SafetyEngine(store)

    async def execute(self, run: AgentRun, emit: StepEmitter) -> AgentState:
        try:
            from langgraph.graph import END, START, StateGraph
        except ImportError as error:
            raise RuntimeError("LangGraph runtime dependencies are not installed") from error

        async def governance(state: AgentState) -> dict[str, Any]:
            record = self.datahub.find_pipeline(run.pipelineId)
            if record is None:
                raise RuntimeError("Pipeline metadata is missing")
            search = await call_mcp_tool(
                self.settings.datahub_mcp_url,
                "search",
                {
                    "query": (
                        "/q refund+policy"
                        if run.pipelineId == "refund"
                        else "/q risk+features"
                    ),
                    "num_results": 5,
                },
            )
            lineage = await call_mcp_tool(
                self.settings.datahub_mcp_url,
                "get_lineage",
                {
                    # DataHub's dataset lineage API is the stable MCP surface; agent/tool
                    # dependencies remain discoverable through Agent Registry search.
                    "urn": REFUND_RAG_URN if run.pipelineId == "refund" else RISK_FEATURES_URN,
                    "upstream": True,
                    "max_hops": 3,
                },
            )
            snapshot = self.datahub.governance_snapshot(run.pipelineId)
            await emit(
                RunStepType.GOVERNANCE_EVIDENCE,
                "DataHub governance evidence loaded",
                "The agent queried DataHub MCP and Aegis captured a direct GMS snapshot.",
                SourceSystem.DATAHUB_MCP,
                {
                    "search": search,
                    "lineage": lineage,
                    "snapshot": snapshot.model_dump(mode="json"),
                },
            )
            return {
                "governance_context": {"search": search, "lineage": lineage},
                "evidence": snapshot,
            }

        async def business_context(state: AgentState) -> dict[str, Any]:
            if run.pipelineId == "refund":
                facts = await call_mcp_tool(
                    self.settings.business_mcp_url,
                    "lookup_case",
                    {"case_id": run.subject.id},
                )
                policy = await call_mcp_tool(
                    self.settings.business_mcp_url,
                    "search_refund_policy",
                    {"query": run.message},
                )
                context: Any = {"case": facts, "policy": policy}
            else:
                context = await call_mcp_tool(
                    self.settings.business_mcp_url,
                    "lookup_account",
                    {"account_id": run.subject.id},
                )
            await emit(
                RunStepType.CONTEXT_RETRIEVAL,
                "Business context retrieved",
                "Read-only business facts were returned by the context MCP service.",
                SourceSystem.BUSINESS_MCP,
                {"context": context},
            )
            return {"business_context": context}

        async def model_proposal(state: AgentState) -> dict[str, Any]:
            proposal = await self._model_proposal(run, state)
            await emit(
                RunStepType.MODEL_RESPONSE,
                "OpenAI model completed reasoning",
                f"{self.settings.openai_model} selected a consequential tool.",
                SourceSystem.OPENAI,
                {"model": self.settings.openai_model},
            )
            await emit(
                RunStepType.TOOL_PROPOSED,
                f"Model proposed {proposal['tool']}",
                "This is the model's genuine function call; it has not reached the executor.",
                SourceSystem.OPENAI,
                {"toolCall": proposal},
            )
            return {"proposal": proposal}

        async def gate(state: AgentState) -> dict[str, Any]:
            # Re-read DataHub immediately before enforcement. Actions events are never trusted here.
            proposal = state["proposal"]
            context = state["business_context"]
            observed_at = context.get("observed_at") if isinstance(context, dict) else None
            evidence = self.datahub.governance_snapshot(
                run.pipelineId, observed_at=observed_at
            )
            binding_error = self._proposal_binding_error(run, proposal, context)
            if binding_error:
                decision = GateDecision(
                    decision=Decision.BLOCK,
                    reasonCode=binding_error,
                    controlId="tool-argument-binding",
                    evidenceSnapshot=evidence,
                )
            elif run.pipelineId == "refund":
                evaluation = self.safety.evaluate(
                    EvaluationInput(
                        environment="PRODUCTION",
                        tool=proposal["tool"],
                        amount=float(proposal["arguments"]["amount"]),
                        approval_status=evidence.approvalStatus,
                        lineage_complete=evidence.lineageComplete,
                        datahub_available=evidence.datahubAvailable,
                    )
                )
                decision = GateDecision(
                    decision=evaluation.decision,
                    reasonCode=evaluation.reasonCode,
                    controlId=evaluation.controlId,
                    evidenceSnapshot=evidence,
                    evaluationId=evaluation.id,
                )
            else:
                evaluation = self.safety.evaluate_risk(
                    RiskEvaluationInput(
                        environment="PRODUCTION",
                        tool=proposal["tool"],
                        observed_at=evidence.observedAt,
                        freshness_sla_seconds=self.settings.risk_freshness_sla_seconds,
                        lineage_complete=evidence.lineageComplete,
                        datahub_available=evidence.datahubAvailable,
                    )
                )
                decision = GateDecision(
                    decision=evaluation.decision,
                    reasonCode=evaluation.reasonCode,
                    controlId=evaluation.controlId,
                    evidenceSnapshot=evidence,
                    evaluationId=evaluation.id,
                )
            await emit(
                RunStepType.GATE_DECISION,
                f"Aegis decision: {decision.decision.value}",
                decision.reasonCode.replace("_", " ").title(),
                SourceSystem.AEGIS,
                {"decision": decision.model_dump(mode="json")},
            )
            return {"decision": decision, "evidence": evidence}

        async def execute_tool(state: AgentState) -> dict[str, Any]:
            decision = state["decision"]
            proposal = state["proposal"]
            if decision.decision != Decision.ALLOW:
                return {"receipt": None}
            arguments = proposal["arguments"]
            token = mint_capability(
                self.settings.capability_signing_secret,
                tool=proposal["tool"],
                arguments=arguments,
                run_id=run.id,
            )
            if proposal["tool"] == "issue_refund":
                mcp_args = {
                    "case_id": arguments["caseId"],
                    "amount": arguments["amount"],
                    "currency": arguments["currency"],
                    "capability_token": token,
                }
            else:
                mcp_args = {
                    "account_id": arguments["accountId"],
                    "capability_token": token,
                }
            receipt = await call_mcp_tool(
                self.settings.business_mcp_url, proposal["tool"], mcp_args
            )
            await emit(
                RunStepType.TOOL_EXECUTED,
                f"Sandbox {proposal['tool']} executed",
                "The MCP executor accepted the exact short-lived Aegis capability.",
                SourceSystem.SIMULATED_EXTERNAL,
                {"receipt": receipt},
            )
            return {"receipt": receipt}

        async def finish(state: AgentState) -> dict[str, Any]:
            decision = state["decision"]
            if decision.decision == Decision.ALLOW:
                output = (
                    "The requested action passed Aegis controls and was recorded in the sandbox."
                )
            elif decision.decision == Decision.REVIEW:
                output = "The action was held for human review and was not sent to the executor."
            else:
                output = (
                    "Aegis blocked the action before execution because required governance "
                    "evidence failed."
                )
            return {"output": output}

        graph = StateGraph(AgentState)
        graph.add_node("governance", governance)
        graph.add_node("business_context", business_context)
        graph.add_node("model_proposal", model_proposal)
        graph.add_node("gate", gate)
        graph.add_node("execute_tool", execute_tool)
        graph.add_node("finish", finish)
        graph.add_edge(START, "governance")
        graph.add_edge("governance", "business_context")
        graph.add_edge("business_context", "model_proposal")
        graph.add_edge("model_proposal", "gate")
        graph.add_edge("gate", "execute_tool")
        graph.add_edge("execute_tool", "finish")
        graph.add_edge("finish", END)
        return await graph.compile().ainvoke({"run": run})

    @staticmethod
    def _proposal_binding_error(
        run: AgentRun, proposal: dict[str, Any], context: Any
    ) -> str | None:
        """Bind model-selected arguments to the admitted subject and verified business facts."""
        arguments = proposal.get("arguments", {})
        if run.pipelineId == "refund":
            case = context.get("case", {}) if isinstance(context, dict) else {}
            if proposal.get("tool") != "issue_refund":
                return "UNEXPECTED_TOOL"
            if arguments.get("caseId") != run.subject.id or case.get("id") != run.subject.id:
                return "SUBJECT_BINDING_FAILED"
            try:
                amount = float(arguments.get("amount"))
                verified_total = float(case.get("order_total"))
            except (TypeError, ValueError):
                return "BUSINESS_FACTS_MISSING"
            if amount <= 0 or amount > verified_total or arguments.get("currency") != case.get(
                "currency"
            ):
                return "BUSINESS_FACT_BINDING_FAILED"
            return None
        if proposal.get("tool") != "freeze_account":
            return "UNEXPECTED_TOOL"
        account_id = context.get("id") if isinstance(context, dict) else None
        if arguments.get("accountId") != run.subject.id or account_id != run.subject.id:
            return "SUBJECT_BINDING_FAILED"
        return None

    async def _model_proposal(self, run: AgentRun, state: AgentState) -> dict[str, Any]:
        try:
            from openai import AsyncOpenAI
        except ImportError as error:
            raise RuntimeError("OpenAI runtime dependency is not installed") from error
        if run.pipelineId == "refund":
            function = {
                "type": "function",
                "name": "issue_refund",
                "description": "Issue a refund for a verified customer case.",
                "strict": True,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "caseId": {"type": "string"},
                        "amount": {"type": "number", "minimum": 0.01, "maximum": 10000},
                        "currency": {"type": "string", "enum": ["USD"]},
                    },
                    "required": ["caseId", "amount", "currency"],
                    "additionalProperties": False,
                },
            }
        else:
            function = {
                "type": "function",
                "name": "freeze_account",
                "description": "Freeze an account with high-confidence fraud signals.",
                "strict": True,
                "parameters": {
                    "type": "object",
                    "properties": {"accountId": {"type": "string"}},
                    "required": ["accountId"],
                    "additionalProperties": False,
                },
            }
        prompt = (
            "You are an operational AI agent. Use the supplied business context to take the "
            "requested action. Governance metadata is context, but Aegis independently "
            "enforces it. "
            "You must call the provided function exactly once.\n\n"
            f"User request: {run.message}\nSubject: {run.subject.model_dump_json()}\n"
            f"Business context: {json.dumps(state['business_context'], default=str)}\n"
            f"DataHub context: {json.dumps(state['governance_context'], default=str)}"
        )
        response = await AsyncOpenAI(api_key=self.settings.openai_api_key).responses.create(
            model=self.settings.openai_model,
            input=prompt,
            tools=[function],
            tool_choice="required",
            reasoning={"effort": self.settings.openai_reasoning_effort},
        )
        for item in response.output:
            if getattr(item, "type", None) == "function_call":
                arguments = json.loads(item.arguments)
                return {
                    "tool": item.name,
                    "arguments": arguments,
                    "callId": item.call_id,
                }
        raise RuntimeError("The model did not produce the required function call")


class AgentRunService:
    def __init__(self, settings: Settings, store: AegisStore, datahub: DataHubAdapter) -> None:
        self.settings = settings
        self.store = store
        self.datahub = datahub
        self.runtime = AgentRuntime(settings, store, datahub)
        self._tasks: set[asyncio.Task[None]] = set()

    def admit(self, pipeline_id: str, body: AgentRunRequest) -> AgentRun:
        if pipeline_id not in EXECUTABLE_PIPELINES:
            raise RunAdmissionError(409, "AGENT_NOT_EXECUTABLE", "This agent is catalog-only.")
        if not self.settings.openai_api_key:
            raise RunAdmissionError(
                503, "MODEL_NOT_CONFIGURED", "Set OPENAI_API_KEY to execute a live agent run."
            )
        if self.settings.data_mode.lower() != "live":
            raise RunAdmissionError(
                409,
                "LIVE_DATAHUB_REQUIRED",
                "Agent execution requires AEGIS_DATA_MODE=live and a reachable DataHub instance.",
            )
        expected_subject = "CASE" if pipeline_id == "refund" else "ACCOUNT"
        if body.subject.type != expected_subject:
            raise RunAdmissionError(
                422, "INVALID_SUBJECT_TYPE", f"{pipeline_id} requires a {expected_subject} subject."
            )
        timestamp = utc_now()
        run = AgentRun(
            id=f"run-{uuid4().hex[:12]}",
            pipelineId=pipeline_id,
            status=RunStatus.QUEUED,
            message=body.message,
            subject=body.subject,
            model=self.settings.openai_model,
            startedAt=timestamp,
            updatedAt=timestamp,
        )
        self.store.save_run(run)
        return run

    def start(self, run: AgentRun) -> None:
        task = asyncio.create_task(self._execute(run.id))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _execute(self, run_id: str) -> None:
        run = self.store.get_run(run_id, include_steps=False)
        if run is None:
            return
        sequence = 0

        async def emit(
            step_type: RunStepType,
            title: str,
            detail: str,
            source: SourceSystem,
            payload: dict[str, Any],
        ) -> None:
            nonlocal sequence
            sequence += 1
            self.store.append_run_step(
                RunStep(
                    id=f"step-{uuid4().hex[:12]}",
                    runId=run.id,
                    sequence=sequence,
                    type=step_type,
                    title=title,
                    detail=detail,
                    sourceSystem=source,
                    occurredAt=utc_now(),
                    payload=payload,
                )
            )

        run.status = RunStatus.RUNNING
        run.updatedAt = utc_now()
        self.store.save_run(run)
        await emit(
            RunStepType.RUN_STARTED,
            "Live agent run started",
            "LangGraph began an authenticated online execution.",
            SourceSystem.AEGIS,
            {"pipelineId": run.pipelineId, "model": run.model},
        )
        try:
            result = await asyncio.wait_for(
                self.runtime.execute(run, emit), timeout=self.settings.run_timeout_seconds
            )
            decision = result["decision"]
            run.proposedToolCall = result["proposal"]
            run.gateDecision = decision
            run.toolReceipt = result.get("receipt")
            run.output = result["output"]
            run.status = {
                Decision.ALLOW: RunStatus.COMPLETED,
                Decision.BLOCK: RunStatus.BLOCKED,
                Decision.REVIEW: RunStatus.REVIEW,
            }[decision.decision]
            run.completedAt = utc_now()
            run.datahubWriteback = await asyncio.to_thread(self._publish_run_outcome, run)
            await emit(
                RunStepType.DATAHUB_WRITEBACK,
                (
                    f"DataHub {run.datahubWriteback.recordType.lower()} written"
                    if run.datahubWriteback.status == "WRITTEN"
                    else f"DataHub {run.datahubWriteback.recordType.lower()} write failed"
                ),
                run.datahubWriteback.detail,
                (
                    SourceSystem.DATAHUB
                    if run.datahubWriteback.status == "WRITTEN"
                    else SourceSystem.AEGIS
                ),
                {"writeback": run.datahubWriteback.model_dump(mode="json")},
            )
            await emit(
                RunStepType.RUN_COMPLETED,
                f"Run {run.status.value.lower()}",
                run.output,
                SourceSystem.AEGIS,
                {"status": run.status.value},
            )
        except Exception as error:
            run.status = RunStatus.FAILED
            run.errorCode = type(error).__name__.upper()
            run.errorDetail = str(error)
            run.output = "The live run failed before a consequential action could execute."
            await emit(
                RunStepType.ERROR,
                "Run failed safely",
                str(error),
                SourceSystem.AEGIS,
                {"errorType": type(error).__name__},
            )
        run.updatedAt = utc_now()
        run.completedAt = run.completedAt or run.updatedAt
        self.store.save_run(run)

    def _publish_run_outcome(self, run: AgentRun) -> DataHubRunWriteback:
        """Write a run security outcome without changing the enforcement result on failure."""
        record_type = "ATTESTATION" if run.status == RunStatus.COMPLETED else "INCIDENT"
        attempted_at = utc_now()
        try:
            if record_type == "ATTESTATION":
                urn = self.datahub.write_run_attestation_document(run)
                detail = (
                    "The allowed, executed run was recorded as a DataHub attestation Document."
                )
            else:
                urn = self.datahub.write_run_incident(run)
                detail = (
                    f"The {run.status.value.lower()} run was recorded as an active DataHub "
                    "security incident."
                )
            return DataHubRunWriteback(
                recordType=record_type,
                status="WRITTEN",
                urn=urn,
                attemptedAt=attempted_at,
                detail=detail,
            )
        except Exception as error:
            return DataHubRunWriteback(
                recordType=record_type,
                status="FAILED",
                attemptedAt=attempted_at,
                detail=(
                    "The enforcement result remains authoritative, but DataHub writeback "
                    f"failed with {type(error).__name__}: {error}"
                ),
            )
