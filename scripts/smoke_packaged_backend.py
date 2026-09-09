"""Launch the packaged backend and verify its public runtime contracts."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXECUTABLE = (
    ROOT / "desktop" / "src-tauri" / "resources" / "nerve-center-api.exe"
)
HEALTH_URL = "http://127.0.0.1:8765/health"
BASE_URL = "http://127.0.0.1:8765"


def read_health() -> dict[str, object] | None:
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=1) as response:  # noqa: S310
            if response.status != 200:
                return None
            return json.loads(response.read().decode("utf-8"))
    except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError):
        return None


def request_json(
    path: str,
    method: str = "GET",
    payload: dict[str, object] | None = None,
) -> dict[str, object] | list[dict[str, object]]:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(  # noqa: S310
        f"{BASE_URL}{path}",
        data=body,
        method=method,
        headers={"Content-Type": "application/json"} if body is not None else {},
    )
    with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
        raw = response.read()
        return json.loads(raw.decode("utf-8")) if raw else {}


def smoke_job_scout_workspace() -> None:
    workspace = request_json("/api/v1/modules/job_scout/workspace")
    if not isinstance(workspace, dict):
        raise SystemExit(f"Unexpected Job Scout workspace payload: {workspace}")
    required = {"configuration", "documents", "profile", "keywords", "sources", "opening_count"}
    missing = sorted(required - workspace.keys())
    if missing:
        raise SystemExit(f"Packaged Job Scout workspace is missing fields: {missing}")
    print("Packaged Job Scout workspace route healthy.")


def smoke_module_runtime(timeout: float) -> None:
    created = request_json(
        "/api/v1/runs",
        "POST",
        {"task_id": "job_scout.discovery", "duration_seconds": 30},
    )
    if not isinstance(created, dict) or not isinstance(created.get("id"), str):
        raise SystemExit(f"Unexpected run creation payload: {created}")
    run_id = created["id"]
    request_json(f"/api/v1/runs/{run_id}/start", "POST")
    deadline = time.monotonic() + timeout
    final: dict[str, object] | None = None
    while time.monotonic() < deadline:
        value = request_json(f"/api/v1/runs/{run_id}")
        if isinstance(value, dict) and value.get("status") in {
            "succeeded",
            "partial",
            "failed",
            "cancelled",
        }:
            final = value
            break
        time.sleep(0.25)
    checkpoint = final.get("checkpoint") if final is not None else None
    if (
        final is None or final.get("status") != "partial"
        or not isinstance(checkpoint, dict)
        or checkpoint.get("terminal_reason") != "no_configured_evidence_or_market"
    ):
        raise SystemExit(f"Packaged empty-workspace run did not stop explicitly: {final}")
    module = request_json("/api/v1/modules/job_scout")
    runtime = module.get("runtime") if isinstance(module, dict) else None
    if not isinstance(runtime, dict) or runtime.get("process_id") is None:
        raise SystemExit(f"Packaged module worker did not report a process: {module}")
    request_json(
        "/api/v1/modules/job_scout",
        "PATCH",
        {"lifecycle_state": "paused"},
    )
    print(
        "Packaged module runtime healthy: "
        f"run={run_id}, worker_pid={runtime['process_id']}"
    )


def stop_process_tree(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        taskkill = shutil.which("taskkill")
        if taskkill is None:
            raise RuntimeError("taskkill is required for packaged Windows smoke cleanup")
        subprocess.run(  # noqa: S603
            [taskkill, "/PID", str(process.pid), "/T", "/F"],
            check=False,
            capture_output=True,
            text=True,
        )
    else:
        process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def remove_data_directory(path: Path, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while True:
        try:
            shutil.rmtree(path)
            return
        except FileNotFoundError:
            return
        except PermissionError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.1)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--executable", type=Path, default=DEFAULT_EXECUTABLE)
    parser.add_argument("--timeout", type=float, default=45.0)
    args = parser.parse_args()

    executable = args.executable.resolve()
    if not executable.is_file():
        raise SystemExit(f"Packaged backend is missing: {executable}")
    if read_health() is not None:
        raise SystemExit("Port 8765 is already serving a health endpoint.")

    creation_flags = 0x08000000 if os.name == "nt" else 0
    data_dir = Path(tempfile.mkdtemp(prefix="nerve-center-package-smoke-"))
    process: subprocess.Popen[str] | None = None
    try:
        environment = os.environ.copy()
        environment["NERVE_CENTER_DATA_DIR"] = str(data_dir)
        process = subprocess.Popen(  # noqa: S603
            [str(executable)],
            cwd=ROOT,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            creationflags=creation_flags,
        )
        deadline = time.monotonic() + args.timeout
        while time.monotonic() < deadline:
            return_code = process.poll()
            if return_code is not None:
                output = process.stdout.read() if process.stdout else ""
                raise SystemExit(
                    f"Packaged backend exited with code {return_code}.\n{output[-4000:]}"
                )
            health = read_health()
            if health is not None:
                if health.get("status") != "ok":
                    raise SystemExit(f"Unexpected health payload: {health}")
                print(f"Packaged backend healthy: {health}")
                smoke_job_scout_workspace()
                smoke_module_runtime(args.timeout)
                return 0
            time.sleep(0.25)
        raise SystemExit(f"Packaged backend did not become healthy in {args.timeout}s.")
    finally:
        if process is not None:
            stop_process_tree(process)
        remove_data_directory(data_dir)


if __name__ == "__main__":
    raise SystemExit(main())
