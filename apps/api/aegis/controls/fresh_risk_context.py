from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from aegis.controls.approved_context_source import EvaluationResult
from aegis.domain.enums import Decision


@dataclass(frozen=True)
class RiskEvaluationInput:
    environment: str
    tool: str
    observed_at: str | None
    freshness_sla_seconds: int
    lineage_complete: bool
    datahub_available: bool


class FreshRiskContext:
    id = "fresh-risk-context"
    name = "FreshRiskContext"
    version = "1"

    def evaluate(self, value: RiskEvaluationInput) -> EvaluationResult:
        age_seconds: int | None = None
        if value.observed_at:
            try:
                observed = datetime.fromisoformat(value.observed_at.replace("Z", "+00:00"))
                age_seconds = max(0, int((datetime.now(UTC) - observed).total_seconds()))
            except ValueError:
                age_seconds = None
        fresh = age_seconds is not None and age_seconds <= value.freshness_sla_seconds
        conditions: list[dict[str, Any]] = [
            self._condition("environment", "EQUALS", "PRODUCTION", value.environment),
            self._condition("tool", "EQUALS", "freeze_account", value.tool),
            self._condition("datahub.available", "EQUALS", True, value.datahub_available),
            self._condition("lineage.complete", "EQUALS", True, value.lineage_complete),
            self._condition(
                "risk.ageSeconds", "LESS_THAN_OR_EQUAL", value.freshness_sla_seconds,
                age_seconds, fresh,
            ),
        ]
        if not value.datahub_available:
            return EvaluationResult(Decision.BLOCK, "DATAHUB_UNAVAILABLE", conditions)
        if not value.lineage_complete:
            return EvaluationResult(Decision.BLOCK, "INCOMPLETE_LINEAGE", conditions)
        if value.observed_at is None or age_seconds is None:
            return EvaluationResult(Decision.BLOCK, "MISSING_RISK_OPERATION", conditions)
        if not fresh:
            return EvaluationResult(Decision.REVIEW, "STALE_RISK_CONTEXT", conditions)
        return EvaluationResult(Decision.ALLOW, "FRESH_RISK_CONTEXT", conditions)

    @staticmethod
    def _condition(
        field: str, operator: str, expected: Any, actual: Any, passed: bool | None = None
    ) -> dict[str, Any]:
        return {
            "field": field,
            "operator": operator,
            "expected": expected,
            "actual": actual,
            "passed": actual == expected if passed is None else passed,
        }
