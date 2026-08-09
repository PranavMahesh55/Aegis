from aegis.domain.enums import IncidentState

ALLOWED_TRANSITIONS: dict[IncidentState, set[IncidentState]] = {
    IncidentState.HEALTHY: {IncidentState.CONTEXT_CHANGED},
    IncidentState.CONTEXT_CHANGED: {IncidentState.BLOCKED},
    IncidentState.BLOCKED: {IncidentState.REMEDIATION_APPLIED},
    IncidentState.REMEDIATION_APPLIED: {IncidentState.RE_EVALUATED},
    IncidentState.RE_EVALUATED: {IncidentState.RESOLVED, IncidentState.BLOCKED},
    IncidentState.RESOLVED: set(),
}


class InvalidTransition(ValueError):
    pass


def require_transition(current: IncidentState, target: IncidentState) -> None:
    if target not in ALLOWED_TRANSITIONS[current]:
        raise InvalidTransition(f"{current} cannot transition to {target}")

