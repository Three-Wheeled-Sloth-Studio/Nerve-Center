import socket
import threading
import time
from pathlib import Path

import httpx
import uvicorn

from nerve_center.api.app import create_app
from nerve_center.config import Settings


def test_job_scout_run_crosses_supervised_process_boundary(tmp_path: Path) -> None:
    port = _available_port()
    app = create_app(Settings(data_dir=tmp_path, port=port, scheduler_poll_seconds=60))
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    client = httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=10)
    try:
        _wait_until(lambda: client.get("/health").status_code == 200)
        created = client.post("/api/v1/sessions", json={"duration_seconds": 30})
        created.raise_for_status()
        session = created.json()
        run_id = session["module_run_ids"]["job_scout"]

        final = _wait_until(
            lambda: _terminal_run(client.get(f"/api/v1/runs/{run_id}").json())
        )
        module = client.get("/api/v1/modules/job_scout").json()

        assert final["status"] == "partial"
        assert final["session_id"] == session["id"]
        assert final["module_priority"] == 100
        assert final["result_metrics"]["terminal_reason"] == "no_configured_evidence_or_market"
        assert module["manifest"]["launch"]["runtime"] == "managed_python"
        assert module["runtime"]["process_id"] is not None
        assert module["runtime"]["work_items_processed"] == 1
        stopped = client.post(f"/api/v1/sessions/{session['id']}/emergency-stop")
        stopped.raise_for_status()
        assert stopped.json()["status"] == "cancelled"
        assert stopped.json()["emergency_stop"] is True
    finally:
        client.close()
        server.should_exit = True
        thread.join(timeout=10)


def _terminal_run(value: dict):
    if value["status"] in {"succeeded", "partial", "failed", "cancelled"}:
        return value
    return None


def _wait_until(operation, timeout_seconds: float = 15):
    deadline = time.monotonic() + timeout_seconds
    last_error = None
    while time.monotonic() < deadline:
        try:
            result = operation()
            if result:
                return result
        except (httpx.ConnectError, httpx.RemoteProtocolError) as error:
            last_error = error
        time.sleep(0.1)
    raise AssertionError("condition was not met before timeout") from last_error


def _available_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])
