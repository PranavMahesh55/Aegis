from aegis.controls.approved_context_source import ApprovedContextSource, EvaluationInput
from aegis.domain.enums import Decision


def evaluate(**overrides: object):
    values = {
        "environment": "PRODUCTION",
        "tool": "issue_refund",
        "amount": 8500,
        "approval_status": "approved",
        "lineage_complete": True,
        "datahub_available": True,
    }
    values.update(overrides)
    return ApprovedContextSource().evaluate(EvaluationInput(**values))  # type: ignore[arg-type]


def test_approved_source_allows() -> None:
    result = evaluate()
    assert result.decision == Decision.ALLOW
    assert result.reason_code == "APPROVED_CONTEXT_SOURCE"


def test_unapproved_high_value_blocks() -> None:
    result = evaluate(approval_status="not_approved")
    assert result.decision == Decision.BLOCK
    assert result.reason_code == "UNAPPROVED_CONTEXT_SOURCE"


def test_missing_approval_blocks() -> None:
    assert evaluate(approval_status=None).reason_code == "MISSING_APPROVAL_METADATA"


def test_incomplete_lineage_blocks() -> None:
    assert evaluate(lineage_complete=False).reason_code == "INCOMPLETE_LINEAGE"


def test_datahub_outage_blocks() -> None:
    assert evaluate(datahub_available=False).reason_code == "DATAHUB_UNAVAILABLE"


def test_threshold_is_strictly_greater_than_2000() -> None:
    result = evaluate(amount=2000, approval_status="not_approved")
    assert result.decision == Decision.ALLOW
    assert result.reason_code == "OUTSIDE_CONTROL_SCOPE"

