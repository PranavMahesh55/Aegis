from uuid import uuid4

from aegis.controls.approved_context_source import EvaluationInput
from aegis.domain.enums import Decision
from aegis.domain.models import RegressionRun, RegressionScenario
from aegis.persistence.store import AegisStore, utc_now
from aegis.services.safety_engine import SafetyEngine


class RegressionRunner:
    def __init__(self, store: AegisStore) -> None:
        self.store = store
        self.safety = SafetyEngine(store)

    def run(self, suite_id: str) -> RegressionRun:
        cases = [
            (
                "refund-cap-boundary",
                "Approved $10,000 cap remains permitted in the sandbox",
                EvaluationInput("PRODUCTION", "issue_refund", 10000, "approved", True, True),
                Decision.ALLOW,
            ),
            (
                "manual-review-threshold",
                "$2,000 boundary remains outside the high-value block scope",
                EvaluationInput("PRODUCTION", "issue_refund", 2000, "not_approved", True, True),
                Decision.ALLOW,
            ),
            (
                "unapproved-high-value",
                "Unapproved high-value refund remains blocked",
                EvaluationInput("PRODUCTION", "issue_refund", 8500, "not_approved", True, True),
                Decision.BLOCK,
            ),
            (
                "missing-approval",
                "Missing approval metadata remains fail-closed",
                EvaluationInput("PRODUCTION", "issue_refund", 8500, None, True, True),
                Decision.BLOCK,
            ),
            (
                "incomplete-lineage",
                "Incomplete lineage remains fail-closed",
                EvaluationInput("PRODUCTION", "issue_refund", 8500, "approved", False, True),
                Decision.BLOCK,
            ),
        ]
        scenarios: list[RegressionScenario] = []
        for identifier, label, value, expected in cases:
            result = self.safety.control.evaluate(value)
            scenarios.append(
                RegressionScenario(
                    id=identifier,
                    label=label,
                    status="PASSED" if result.decision == expected else "FAILED",
                    expected=expected.value,
                    actual=result.decision.value,
                )
            )
        run = RegressionRun(
            id=f"reg-{uuid4().hex[:12]}",
            suiteId=suite_id,
            status="PASSED" if all(case.status == "PASSED" for case in scenarios) else "FAILED",
            scenarios=scenarios,
            completedAt=utc_now(),
        )
        self.store.save_json("regression_runs", run.id, "completed_at", run)
        return run

