from fastapi import FastAPI
from fastapi.testclient import TestClient

from aegis.main import SPAStaticFiles


def test_spa_routes_fall_back_to_index_but_missing_assets_stay_404(tmp_path) -> None:
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<main>Aegis shell</main>", encoding="utf-8")
    app = FastAPI()
    app.mount("/", SPAStaticFiles(directory=tmp_path, html=True))

    with TestClient(app) as client:
        response = client.get("/incidents/aegis-4821")
        missing_asset = client.get("/assets/not-real.js")

    assert response.status_code == 200
    assert "Aegis shell" in response.text
    assert response.headers["cache-control"] == "no-store, no-cache, must-revalidate"
    assert response.headers["pragma"] == "no-cache"
    assert missing_asset.status_code == 404
