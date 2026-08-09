from uuid import uuid4

from aegis.controls.approved_context_source import (
    ApprovedContextSource,
    EvaluationInput,
)
from aegis.controls.fresh_risk_context import FreshRiskContext, RiskEvaluationInput
from aegis.domain.models import ConditionResult, ControlEvaluation
from aegis.persistence.store import AegisStore, utc_now


class SafetyEngine:
    def __init__(self, store: AegisStore) -> None:
        self.store = store
        self.control = ApprovedContextSource()
        self.risk_control = FreshRiskContext()

    def evaluate(self, value: EvaluationInput) -> ControlEvaluation:
        return self._persist(self.control, self.control.evaluate(value))

    def evaluate_risk(self, value: RiskEvaluationInput) -> ControlEvaluation:
        return self._persist(self.risk_control, self.risk_control.evaluate(value))

    def _persist(self, control: object, result: object) -> ControlEvaluation:
        evaluation_id = f"eval-{uuid4().hex[:12]}"
        conditions = [
            ConditionResult(
                **condition,
                evidenceId=f"evidence-{condition['field'].replace('.', '-')}",
            )
            for condition in result.conditions
        ]
        evaluation = ControlEvaluation(
            id=evaluation_id,
            controlId=control.id,
            decision=result.decision,
            reasonCode=result.reason_code,
            conditionResults=conditions,
            evidenceIds=[item.evidenceId for item in conditions if item.evidenceId],
            evaluatedAt=utc_now(),
        )
        self.store.save_json("evaluations", evaluation.id, "evaluated_at", evaluation)
        return evaluation
