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


def test_overlapping_active_sessions_are_rejected(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path))

    with TestClient(app) as client:
        first = client.post("/api/v1/sessions", json={"duration_seconds": 60})
        second = client.post("/api/v1/sessions", json={"duration_seconds": 60})
        client.post(f"/api/v1/sessions/{first.json()['id']}/emergency-stop")

    assert first.status_code == 201
    assert second.status_code == 409
    assert "overlaps active session" in second.json()["detail"]


def test_durable_work_queue_api_lifecycle(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path))

    with TestClient(app) as client:
        run = client.post(
            "/api/v1/runs",
            json={"task_id": "job_scout.discovery", "duration_seconds": 60},
        ).json()
        payload = {
            "module_id": "job_scout",
            "run_id": run["id"],
            "task_id": "job_scout.evaluate_fit",
            "work_class": "llm",
            "payload": {"job_id": "job-1"},
            "output_contract": {"type": "object"},
            "idempotency_key": "job-1-fit-v1",
            "module_priority": 100,
            "task_priority": 80,
        }
        created = client.post("/api/v1/work-requests", json=payload)
        duplicate = client.post("/api/v1/work-requests", json=payload)
        queue_status = client.get(
            "/api/v1/work-requests/status", params={"module_id": "job_scout"}
        )
        attempt = client.post(
            "/api/v1/work-requests/claim",
            json={"worker_id": "provider-1", "work_classes": ["llm"]},
        )
        completed = client.post(
            f"/api/v1/work-attempts/{attempt.json()['id']}/complete",
            json={"payload": {"fit": "strong"}},
        )
        attempts = client.get(
            f"/api/v1/work-requests/{created.json()['id']}/attempts"
        )

        queue = app.state.work_queue
        first_delivery = queue.deliver_results("job_scout")
        second_delivery = queue.deliver_results("job_scout")
        queue.acknowledge(completed.json()["id"], "job_scout")

    assert created.status_code == 201
    assert duplicate.json()["id"] == created.json()["id"]
    assert queue_status.json()["queued"] == 1
    assert attempt.json()["number"] == 1
    assert completed.json()["payload"] == {"fit": "strong"}
    assert len(attempts.json()) == 1
    assert first_delivery[0].id == second_delivery[0].id
    assert second_delivery[0].delivery_count == 2
    assert queue.get(created.json()["id"]).status.value == "acknowledged"
