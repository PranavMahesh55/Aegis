from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("AEGIS_DATABASE_PATH", str(tmp_path / "aegis-test.db"))
    monkeypatch.setenv(
        "AEGIS_CONTEXT_DATABASE_PATH", str(tmp_path / "aegis-context-test.db")
    )
    monkeypatch.setenv("AEGIS_DATA_MODE", "seeded")
    monkeypatch.setenv("AEGIS_PRIME_BLOCKED", "true")
    # Explicitly override a developer's local .env so admission tests remain
    # deterministic even when live execution is configured on the workstation.
    monkeypatch.setenv("OPENAI_API_KEY", "")
    from aegis.config import get_settings

    get_settings.cache_clear()
    from aegis.main import app

    with TestClient(app) as test_client:
        yield test_client
    get_settings.cache_clear()
