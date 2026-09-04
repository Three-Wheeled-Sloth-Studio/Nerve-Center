"""Run a bounded supplemental Job Scout session against configured public sources.

This is intentionally not a required CI gate. It exercises the installed local API,
configured Job Scout evidence, ordinary public discovery, manager-owned session control,
and final coverage telemetry without automating applications or outreach.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

_TERMINAL_STATUSES = {"succeeded", "partial", "failed", "cancelled"}
_ACCEPTABLE_STATUSES = {"succeeded", "partial"}


def request_json(
    endpoint: str,
    path: str,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    *,
    timeout: float = 15.0,
) -> Any:
    data = None
    headers: dict[str, str] = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        f"{endpoint.rstrip('/')}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def workspace_ready(workspace: dict[str, Any]) -> bool:
    keywords = workspace.get("keywords") or {}
    profile = workspace.get("profile") or {}
    return bool(
        keywords.get("keywords")
        or workspace.get("sources")
        or profile.get("claims")
        or profile.get("hypotheses")
    )


def coverage_snapshot(run: dict[str, Any]) -> dict[str, Any]:
    checkpoint = run.get("checkpoint") or {}
    coverage = checkpoint.get("coverage") or {}
    if not isinstance(coverage, dict):
        return {}
    return {
        key: value
        for key, value in coverage.items()
        if isinstance(value, (int, float, str, bool))
    }


def run_live_smoke(
    endpoint: str,
    *,
    duration_seconds: int,
    poll_seconds: float,
    output: Path | None,
) -> int:
    health = request_json(endpoint, "/health")
    print(f"Nerve Center healthy: version={health.get('version', 'unknown')}")

    workspace = request_json(endpoint, "/api/v1/modules/job_scout/workspace")
    if not isinstance(workspace, dict) or not workspace_ready(workspace):
        print(
            "Job Scout is not ready for a live smoke. Load a resume/career profile or "
            "configure durable discovery sources first."
        )
        return 2

    keyword_count = len((workspace.get("keywords") or {}).get("keywords") or [])
    source_count = len(workspace.get("sources") or [])
    opening_count = int(workspace.get("opening_count") or 0)
    print(
        "Preflight ready: "
        f"keywords={keyword_count}, durable_sources={source_count}, "
        f"existing_openings={opening_count}"
    )

    session = request_json(
        endpoint,
        "/api/v1/sessions",
        "POST",
        {"duration_seconds": duration_seconds},
    )
    if not isinstance(session, dict):
        raise RuntimeError(f"Unexpected session response: {session!r}")
    run_id = str((session.get("module_run_ids") or {}).get("job_scout") or "")
    if not run_id:
        raise RuntimeError(f"Session did not create a Job Scout run: {session!r}")
    print(
        f"Live Job Scout session started: session={session['id']}, run={run_id}, "
        f"duration={duration_seconds}s"
    )

    last_coverage: dict[str, Any] = {}
    final: dict[str, Any] | None = None
    deadline = time.monotonic() + duration_seconds + 60
    while time.monotonic() < deadline:
        run = request_json(endpoint, f"/api/v1/runs/{run_id}")
        if not isinstance(run, dict):
            raise RuntimeError(f"Unexpected run response: {run!r}")
        current_coverage = coverage_snapshot(run)
        if current_coverage and current_coverage != last_coverage:
            print("Coverage: " + json.dumps(current_coverage, sort_keys=True))
            last_coverage = current_coverage
        if run.get("status") in _TERMINAL_STATUSES:
            final = run
            break
        time.sleep(poll_seconds)

    if final is None:
        print("Live Job Scout session did not reach a terminal state before the safety timeout.")
        return 3

    metrics = final.get("result_metrics") or {}
    report = {
        "session_id": session.get("id"),
        "run_id": run_id,
        "status": final.get("status"),
        "summary": final.get("result_summary"),
        "coverage": metrics,
    }
    print("Final live-smoke report:")
    print(json.dumps(report, indent=2, sort_keys=True))
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        print(f"Saved report: {output}")

    return 0 if final.get("status") in _ACCEPTABLE_STATUSES else 1


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument(
        "--endpoint",
        default="http://127.0.0.1:8765",
        help="Running Nerve Center local API endpoint.",
    )
    result.add_argument(
        "--duration-seconds",
        type=int,
        default=300,
        help="Authorized manager work-session duration. Default: 300.",
    )
    result.add_argument(
        "--poll-seconds",
        type=float,
        default=2.0,
        help="Run-status polling interval. Default: 2.0.",
    )
    result.add_argument(
        "--output",
        type=Path,
        help="Optional local JSON report path.",
    )
    return result


def main() -> int:
    args = parser().parse_args()
    if args.duration_seconds < 30:
        raise SystemExit("--duration-seconds must be at least 30")
    if args.poll_seconds <= 0:
        raise SystemExit("--poll-seconds must be positive")
    try:
        return run_live_smoke(
            args.endpoint,
            duration_seconds=args.duration_seconds,
            poll_seconds=args.poll_seconds,
            output=args.output,
        )
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        print(f"Live Job Scout smoke could not reach the local API: {error}")
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
