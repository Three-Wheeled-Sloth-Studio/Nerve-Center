from pathlib import Path

from fastapi.testclient import TestClient

from nerve_center.api.app import create_app
from nerve_center.config import Settings


def test_health(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path))

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert (tmp_path / "nerve-center.sqlite3").exists()
