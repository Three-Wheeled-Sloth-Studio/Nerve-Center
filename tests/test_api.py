from pathlib import Path

from fastapi.testclient import TestClient

from nerve_center.api.app import create_app
from nerve_center.config import Settings


def test_health_and_run_lifecycle(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path))

    with TestClient(app) as client:
        health = client.get("/health")
        created = client.post(
            "/api/v1/runs",
            json={
                "task_id": "synthetic",
                "duration_seconds": 60,
                "configuration": {"iterations": 2},
            },
        )
        run_id = created.json()["id"]
        cancelled = client.post(f"/api/v1/runs/{run_id}/cancel")
        fetched = client.get(f"/api/v1/runs/{run_id}")

    assert health.status_code == 200
    assert created.status_code == 201
    assert cancelled.json()["status"] == "cancelled"
    assert fetched.json()["status"] == "cancelled"
    assert (tmp_path / "nerve-center.sqlite3").exists()


def test_unknown_task_is_rejected(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path))

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/runs",
            json={"task_id": "not-real", "duration_seconds": 60},
        )

    assert response.status_code == 404
