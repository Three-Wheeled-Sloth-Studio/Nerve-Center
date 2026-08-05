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
        events = client.get(f"/api/v1/runs/{run_id}/events")

    assert health.status_code == 200
    assert created.status_code == 201
    assert cancelled.json()["status"] == "cancelled"
    assert fetched.json()["status"] == "cancelled"
    assert events.status_code == 200
    assert len(events.json()) >= 2
    assert (tmp_path / "nerve-center.sqlite3").exists()


def test_unknown_task_is_rejected(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path))

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/runs",
            json={"task_id": "not-real", "duration_seconds": 60},
        )

    assert response.status_code == 404


def test_module_inventory_and_pause_gate_run_admission(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path))

    with TestClient(app) as client:
        modules = client.get("/api/v1/modules")
        paused = client.patch(
            "/api/v1/modules/job_scout",
            json={"lifecycle_state": "paused"},
        )
        rejected = client.post(
            "/api/v1/runs",
            json={"task_id": "job_scout.discovery", "duration_seconds": 60},
        )
        resumed = client.patch(
            "/api/v1/modules/job_scout",
            json={"lifecycle_state": "enabled"},
        )

    assert modules.status_code == 200
    assert modules.json()[0]["manifest"]["module_id"] == "job_scout"
    assert paused.json()["lifecycle_state"] == "paused"
    assert rejected.status_code == 409
    assert resumed.json()["lifecycle_state"] == "enabled"


def test_paused_module_cannot_start_previously_queued_run(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path))

    with TestClient(app) as client:
        created = client.post(
            "/api/v1/runs",
            json={"task_id": "job_scout.discovery", "duration_seconds": 60},
        )
        client.patch(
            "/api/v1/modules/job_scout",
            json={"lifecycle_state": "paused"},
        )
        started = client.post(f"/api/v1/runs/{created.json()['id']}/start")

    assert created.status_code == 201
    assert started.status_code == 409
    assert "module job_scout is paused" in started.json()["detail"]


def test_recurring_session_persists_concrete_next_window(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path))

    with TestClient(app) as client:
        created = client.post(
            "/api/v1/sessions",
            json={
                "recurrence_timezone": "America/New_York",
                "recurrence_local_start_time": "18:00",
                "recurrence_duration_seconds": 3600,
                "recurrence_weekdays": [0, 1, 2, 3, 4],
            },
        )

    assert created.status_code == 201
    assert created.json()["status"] == "scheduled"
    assert created.json()["starts_at"] < created.json()["ends_at"]
    assert created.json()["recurrence"]["timezone"] == "America/New_York"
