from pathlib import Path

from aegis.persistence.store import AegisStore


def test_reset_is_deterministic(tmp_path: Path) -> None:
    store = AegisStore(tmp_path / "state.db", prime_blocked=True)
    first = store.reset(blocked=False)
    store.update_state(incident_state="CONTEXT_CHANGED", version=1, source_approved=0)
    second = store.reset(blocked=False)
    keys = {"incident_state", "version", "active_source", "source_approved", "writeback_state"}
    assert {key: first[key] for key in keys} == {key: second[key] for key in keys}

