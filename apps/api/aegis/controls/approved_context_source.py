from dataclasses import dataclass
from typing import Any

from aegis.domain.enums import Decision


@dataclass(frozen=True)
class EvaluationInput:
    environment: str
    tool: str
    amount: float
    approval_status: str | None
    lineage_complete: bool
    datahub_available: bool


@dataclass(frozen=True)
class EvaluationResult:
    decision: Decision
    reason_code: str
    conditions: list[dict[str, Any]]


class ApprovedContextSource:
    id = "approved-context-source"
    name = "ApprovedContextSource"
    version = "1"

    def evaluate(self, value: EvaluationInput) -> EvaluationResult:
        conditions = [
            self._condition("environment", "EQUALS", "PRODUCTION", value.environment),
            self._condition("tool", "EQUALS", "issue_refund", value.tool),
            self._condition("amount", "GREATER_THAN", 2000, value.amount, value.amount > 2000),
            self._condition(
                "context.approvalStatus",
                "EQUALS",
                "approved",
                value.approval_status,
            ),
            self._condition("lineage.complete", "EQUALS", True, value.lineage_complete),
            self._condition("datahub.available", "EQUALS", True, value.datahub_available),
        ]
        consequential = (
            value.environment == "PRODUCTION"
            and value.tool == "issue_refund"
            and value.amount > 2000
        )
        if not consequential:
            return EvaluationResult(Decision.ALLOW, "OUTSIDE_CONTROL_SCOPE", conditions)
        if not value.datahub_available:
            return EvaluationResult(Decision.BLOCK, "DATAHUB_UNAVAILABLE", conditions)
        if not value.lineage_complete:
            return EvaluationResult(Decision.BLOCK, "INCOMPLETE_LINEAGE", conditions)
        if value.approval_status is None:
            return EvaluationResult(Decision.BLOCK, "MISSING_APPROVAL_METADATA", conditions)
        if value.approval_status != "approved":
            return EvaluationResult(Decision.BLOCK, "UNAPPROVED_CONTEXT_SOURCE", conditions)
        return EvaluationResult(Decision.ALLOW, "APPROVED_CONTEXT_SOURCE", conditions)

    @staticmethod
    def _condition(
        field: str,
        operator: str,
        expected: Any,
        actual: Any,
        passed: bool | None = None,
    ) -> dict[str, Any]:
        return {
            "field": field,
            "operator": operator,
            "expected": expected,
            "actual": actual,
            "passed": actual == expected if passed is None else passed,
        }

