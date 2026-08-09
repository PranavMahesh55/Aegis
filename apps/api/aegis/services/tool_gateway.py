from typing import Any
from uuid import uuid4

from aegis.controls.approved_context_source import EvaluationInput
from aegis.domain.enums import Decision
from aegis.domain.models import ControlEvaluation, ToolCall
from aegis.persistence.store import AegisStore, utc_now
from aegis.services.safety_engine import SafetyEngine


class SimulatedRefundExecutor:
    def __init__(self, store: AegisStore) -> None:
        self.store = store

    def execute(self, call: ToolCall) -> dict[str, Any]:
        receipt = {
            "id": f"sim-refund-{uuid4().hex[:10]}",
            "status": "SIMULATED_ACCEPTED",
            "amount": call.amount,
            "currency": call.currency,
            "caseId": call.caseId,
            "createdAt": utc_now(),
            "sourceSystem": "SIMULATED_EXTERNAL",
        }
        self.store.save_json("tool_receipts", receipt["id"], "created_at", receipt)
        return receipt


class ToolGateway:
    def __init__(self, store: AegisStore) -> None:
        self.store = store
        self.safety = SafetyEngine(store)
        self.executor = SimulatedRefundExecutor(store)

    def intercept(
        self,
        call: ToolCall,
        *,
        approval_status: str | None,
        lineage_complete: bool,
        datahub_available: bool,
    ) -> tuple[ControlEvaluation, dict[str, Any] | None]:
        evaluation = self.safety.evaluate(
            EvaluationInput(
                environment="PRODUCTION",
                tool=call.tool,
                amount=call.amount,
                approval_status=approval_status,
                lineage_complete=lineage_complete,
                datahub_available=datahub_available,
            )
        )
        receipt = self.executor.execute(call) if evaluation.decision == Decision.ALLOW else None
        return evaluation, receipt

