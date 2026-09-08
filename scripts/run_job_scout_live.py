"""Run a durable, unattended Job Scout discovery and scoring evaluation.

The runner can own a source API process, load a real resume into the configured
local data directory, execute a bounded manager session, score a sample of retained
openings, and continuously checkpoint a privacy-sensitive local JSON report.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from typing import Any

from platformdirs import user_data_path

from nerve_center.scoring.fit import FIT_ANALYSIS_CONTRACT_VERSION

TERMINAL_STATUSES = {"succeeded", "partial", "failed", "cancelled"}
HEARTBEAT_SECONDS = 60.0


def print_progress(message: str) -> None:
    timestamp = datetime.now().astimezone().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}", flush=True)


class ProgressReporter:
    """Emit transitions immediately and a quiet heartbeat while state is unchanged."""

    def __init__(
        self,
        heartbeat_seconds: float = HEARTBEAT_SECONDS,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.heartbeat_seconds = heartbeat_seconds
        self.clock = clock
        self.last_signature: tuple[object, ...] | None = None
        self.last_emitted_at = 0.0

    def observe_run(self, run: dict[str, Any]) -> str | None:
        checkpoint = dict(run.get("checkpoint") or {})
        status = str(run.get("status") or "unknown")
        phase = str(checkpoint.get("phase") or status)
        cycle = int(checkpoint.get("discovery_cycle") or 0)
        counts = _progress_counts(
            dict(checkpoint.get("coverage") or run.get("result_metrics") or {})
        )
        detail = f"discovery {phase}"
        if cycle:
            detail += f" cycle={cycle}"
        return self._observe(("discovery", status, phase, cycle, counts), detail, counts)

    def observe_manager(
        self,
        session: dict[str, Any],
        queue: dict[str, Any],
    ) -> str | None:
        status = str(session.get("status") or "unknown")
        phase = str(session.get("admission_phase") or status)
        counts = (
            ("queued", int(queue.get("queued", 0))),
            ("claimed", int(queue.get("claimed", 0))),
        )
        detail = f"manager {phase}"
        return self._observe(("manager", status, phase, counts), detail, counts)

    def _observe(
        self,
        signature: tuple[object, ...],
        detail: str,
        counts: tuple[tuple[str, int], ...],
    ) -> str | None:
        now = self.clock()
        transition = signature != self.last_signature
        if not transition and now - self.last_emitted_at < self.heartbeat_seconds:
            return None
        prefix = "" if transition else "heartbeat | "
        suffix = "".join(f" | {label}={value}" for label, value in counts)
        message = f"{prefix}{detail}{suffix}"
        print_progress(message)
        self.last_signature = signature
        self.last_emitted_at = now
        return message


def _progress_counts(values: dict[str, Any]) -> tuple[tuple[str, int], ...]:
    labels = (
        ("strategies_attempted", "strategies"),
        ("results_examined", "results"),
        ("companies_discovered", "companies"),
        ("career_sources_resolved", "sources"),
        ("postings_inspected", "postings"),
        ("opportunities_retained", "roles"),
        ("provider_warning_count", "warnings"),
    )
    return tuple(
        (label, int(values[key]))
        for key, label in labels
        if key in values and isinstance(values[key], (int, float))
    )


def request_json(
    endpoint: str,
    path: str,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    *,
    timeout: float = 30.0,
) -> Any:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"} if payload is not None else {}
    request = urllib.request.Request(
        f"{endpoint.rstrip('/')}{path}", data=data, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:2000]
        raise RuntimeError(f"{method} {path} returned HTTP {error.code}: {detail}") from error


class ManagedApi:
    def __init__(
        self,
        endpoint: str,
        data_dir: Path,
        log_path: Path,
        default_model: str,
    ) -> None:
        self.endpoint = endpoint
        self.data_dir = data_dir
        self.log_path = log_path
        self.default_model = default_model
        self.process: subprocess.Popen[bytes] | None = None
        self._log: Any = None

    def __enter__(self) -> ManagedApi:
        try:
            request_json(self.endpoint, "/health", timeout=1)
        except (OSError, RuntimeError):
            pass
        else:
            raise RuntimeError(f"Refusing to replace an API already listening at {self.endpoint}")

        parsed = urllib.parse.urlsplit(self.endpoint)
        if parsed.hostname not in {"127.0.0.1", "localhost"} or parsed.port is None:
            raise ValueError("--endpoint must be a loopback URL with an explicit port")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._log = self.log_path.open("ab")
        environment = os.environ.copy()
        environment["NERVE_CENTER_HOST"] = "127.0.0.1"
        environment["NERVE_CENTER_PORT"] = str(parsed.port)
        environment["NERVE_CENTER_DATA_DIR"] = str(self.data_dir)
        environment["NERVE_CENTER_OLLAMA_DEFAULT_MODEL"] = self.default_model
        environment["NERVE_CENTER_OLLAMA_SCHEMA_FALLBACK_MODEL"] = "qwen2.5:7b-instruct"
        environment["NERVE_CENTER_OLLAMA_ALLOW_MODEL_FALLBACK"] = "true"
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        self.process = subprocess.Popen(
            [sys.executable, "-c", "from nerve_center.api.app import run; run()"],
            env=environment,
            stdout=self._log,
            stderr=subprocess.STDOUT,
            creationflags=flags,
        )
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError(
                    f"Nerve Center API exited with {self.process.returncode}; see {self.log_path}"
                )
            try:
                request_json(self.endpoint, "/health", timeout=2)
                return self
            except (OSError, RuntimeError):
                time.sleep(0.5)
        raise RuntimeError(f"Nerve Center API did not become healthy; see {self.log_path}")

    def __exit__(self, *_exc: object) -> None:
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            with suppress(subprocess.TimeoutExpired):
                self.process.wait(timeout=15)
            if self.process.poll() is None:
                self.process.kill()
        if self._log is not None:
            self._log.close()


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def archive_report(path: Path, report: dict[str, Any]) -> None:
    """Keep an immutable-by-convention report for each durable discovery run."""
    run_id = str((report.get("session") or {}).get("run_id") or "").strip()
    if run_id:
        write_report(path.with_name(f"run-{run_id}.json"), report)


def configure_workspace(
    endpoint: str,
    *,
    resume: Path | None,
    analyze_resume: bool,
    target_titles: list[str],
    locations: list[str],
    remote_preference: str,
) -> dict[str, Any]:
    workspace = request_json(endpoint, "/api/v1/modules/job_scout/workspace")
    configuration = dict(workspace.get("configuration") or {})
    if target_titles:
        configuration["target_titles"] = target_titles
    if locations:
        configuration["locations"] = locations
    configuration["remote_preference"] = remote_preference
    workspace = request_json(
        endpoint,
        "/api/v1/modules/job_scout/config",
        "PUT",
        configuration,
    )
    if resume is not None:
        workspace = request_json(
            endpoint,
            "/api/v1/modules/job_scout/resume",
            "POST",
            {"path": str(resume.resolve()), "analyze_resume": analyze_resume},
            timeout=900,
        )
    return workspace


def monitor_session(
    endpoint: str,
    duration_seconds: int,
    poll_seconds: float,
    report_path: Path,
    report: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    progress = ProgressReporter()
    session = request_json(
        endpoint,
        "/api/v1/sessions",
        "POST",
        {"duration_seconds": duration_seconds},
    )
    run_id = str((session.get("module_run_ids") or {}).get("job_scout") or "")
    if not run_id:
        raise RuntimeError("Manager session did not create a Job Scout run")
    print_progress(f"discovery scheduled | duration={duration_seconds}s | run={run_id}")
    report["session"] = {"id": session.get("id"), "run_id": run_id}
    write_report(report_path, report)
    deadline = time.monotonic() + duration_seconds + 180
    final: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        run = request_json(endpoint, f"/api/v1/runs/{run_id}")
        report["run"] = {
            "status": run.get("status"),
            "summary": run.get("result_summary"),
            "checkpoint": run.get("checkpoint"),
            "result_metrics": run.get("result_metrics"),
        }
        write_report(report_path, report)
        progress.observe_run(run)
        if run.get("status") in TERMINAL_STATUSES:
            final = run
            break
        time.sleep(poll_seconds)
    if final is None:
        raise RuntimeError("Job Scout session exceeded its safety deadline")
    session_id = str(session["id"])
    while time.monotonic() < deadline:
        session_state = request_json(endpoint, f"/api/v1/sessions/{session_id}")
        queue_state = request_json(
            endpoint, "/api/v1/work-requests/status?module_id=job_scout"
        )
        report["manager_session"] = {
            "status": session_state.get("status"),
            "admission_phase": session_state.get("admission_phase"),
            "queue": queue_state,
        }
        write_report(report_path, report)
        progress.observe_manager(session_state, queue_state)
        active_queue = int(queue_state.get("queued", 0)) + int(
            queue_state.get("claimed", 0)
        )
        if (
            session_state.get("status") in {"completed", "cancelled", "missed", "failed"}
            and active_queue == 0
        ):
            break
        time.sleep(poll_seconds)
    return final, run_id


def score_candidates(
    endpoint: str,
    opportunities: list[dict[str, Any]],
    limit: int,
    model: str,
    report_path: Path,
    report: dict[str, Any],
) -> list[dict[str, Any]]:
    selected = [
        item
        for item in opportunities
        if not (
            (item.get("score") or {}).get("calculation", {}).get("fit_model") == model
            and (item.get("score") or {})
            .get("calculation", {})
            .get("fit_contract_version")
            == FIT_ANALYSIS_CONTRACT_VERSION
        )
    ][:limit]
    scored: list[dict[str, Any]] = []
    failures = 0
    print_progress(f"scoring started | candidates={len(selected)} | model={model}")
    for index, opportunity in enumerate(selected, start=1):
        job = dict(opportunity.get("opening") or {})
        item: dict[str, Any] = {
            "job_id": job.get("id"),
            "title": job.get("title"),
            "company_id": job.get("company_id"),
            "canonical_url": job.get("canonical_url"),
            "provisional_score": opportunity.get("score"),
        }
        try:
            fit = request_json(
                endpoint,
                f"/api/v1/scoring/jobs/{job['id']}/fit",
                "POST",
                {},
                timeout=900,
            )
            score = request_json(
                endpoint,
                f"/api/v1/scoring/jobs/{job['id']}/scores",
                "POST",
                {"fit_analysis_id": fit["id"]},
            )
            item.update({"fit": fit, "score": score, "status": "succeeded"})
        except (OSError, RuntimeError, KeyError) as error:
            item.update({"status": "fit_failed", "error": str(error)[:2000]})
        scored.append(item)
        report["scoring"] = {"completed": index, "requested": len(selected), "items": scored}
        write_report(report_path, report)
        failures = sum(entry.get("status") != "succeeded" for entry in scored)
        print_progress(
            f"scoring {index}/{len(selected)} | succeeded={index - failures} | failures={failures}"
        )
    print_progress(
        f"scoring completed | succeeded={len(scored) - failures} | failures={failures}"
    )
    return scored


def run(args: argparse.Namespace) -> int:
    data_dir = args.data_dir.resolve()
    report_path = args.report or data_dir / "live-tests" / "latest.json"
    report: dict[str, Any] = {
        "status": "starting",
        "data_dir": str(data_dir),
        "resume_file_name": args.resume.name if args.resume else None,
        "target_titles": args.target_title,
        "locations": args.location,
        "duration_seconds": args.duration_seconds,
        "default_model": args.model,
    }
    write_report(report_path, report)
    print_progress(
        f"runner starting | duration={args.duration_seconds}s | score_limit={args.score_limit}"
    )
    context = ManagedApi(
        args.endpoint,
        data_dir,
        data_dir / "logs" / "live-runner-api.log",
        args.model,
    )
    try:
        with context:
            health = request_json(args.endpoint, "/health")
            print_progress(f"API ready | version={health.get('version', 'unknown')}")
            workspace = configure_workspace(
                args.endpoint,
                resume=args.resume,
                analyze_resume=args.analyze_resume,
                target_titles=args.target_title,
                locations=args.location,
                remote_preference=args.remote_preference,
            )
            report.update(
                {
                    "status": "discovering",
                    "health": health,
                    "workspace": {
                        "keyword_count": len(
                            (workspace.get("keywords") or {}).get("keywords") or []
                        ),
                        "source_count": len(workspace.get("sources") or []),
                        "profile_claim_count": len(
                            (workspace.get("profile") or {}).get("claims") or []
                        ),
                    },
                }
            )
            print_progress(
                "workspace ready"
                f" | keywords={report['workspace']['keyword_count']}"
                f" | sources={report['workspace']['source_count']}"
                f" | claims={report['workspace']['profile_claim_count']}"
            )
            final, run_id = monitor_session(
                args.endpoint,
                args.duration_seconds,
                args.poll_seconds,
                report_path,
                report,
            )
            jobs = request_json(args.endpoint, "/api/v1/discovery/jobs")
            opportunities = request_json(
                args.endpoint,
                "/api/v1/review/opportunities?sort=priority&limit=1000",
            )
            companies = request_json(args.endpoint, "/api/v1/discovery/companies")
            sources = request_json(args.endpoint, "/api/v1/discovery/sources")
            strategies = request_json(
                args.endpoint, "/api/v1/modules/job_scout/discovery/strategies"
            )
            reflections = request_json(
                args.endpoint,
                f"/api/v1/modules/job_scout/discovery/sessions/{run_id}/reflections",
            )
            report["inventory"] = {
                "jobs": len(jobs),
                "companies": len(companies),
                "sources": len(sources),
                "strategies": len(strategies),
                "attempted_strategies": sum(bool(item.get("attempts")) for item in strategies),
                "promoted_strategies": sum(
                    item.get("influence") == "positive" for item in strategies
                ),
                "downweighted_strategies": sum(
                    item.get("influence") in {"negative", "deprioritized"} for item in strategies
                ),
                "reflection_hypotheses": len(reflections),
            }
            print_progress(
                "inventory captured"
                f" | roles={report['inventory']['jobs']}"
                f" | companies={report['inventory']['companies']}"
                f" | sources={report['inventory']['sources']}"
                f" | strategies={report['inventory']['strategies']}"
            )
            report["ranked_opportunities"] = opportunities
            report["strategies"] = strategies
            report["reflections"] = reflections
            report["run"]["status"] = final.get("status")
            report["status"] = "scoring"
            write_report(report_path, report)
            score_candidates(
                args.endpoint,
                opportunities,
                args.score_limit,
                args.model,
                report_path,
                report,
            )
            report["model_evidence"] = {
                task_id: request_json(
                    args.endpoint,
                    f"/api/v1/providers/evidence/{urllib.parse.quote(task_id, safe='')}",
                )
                for task_id in ("job_scout.discovery.reflect", FIT_ANALYSIS_CONTRACT_VERSION)
            }
            report["ranked_opportunities"] = request_json(
                args.endpoint,
                "/api/v1/review/opportunities?sort=priority&limit=1000",
            )
            report["status"] = "completed"
            write_report(report_path, report)
            archive_report(report_path, report)
            print_progress(f"live evaluation complete | report={report_path}")
            return 0 if final.get("status") in {"succeeded", "partial"} else 1
    except KeyboardInterrupt:
        session_id = (report.get("session") or {}).get("id")
        if session_id:
            with suppress(OSError, RuntimeError):
                request_json(
                    args.endpoint, f"/api/v1/sessions/{session_id}/emergency-stop", "POST", {}
                )
        report["status"] = "interrupted"
        write_report(report_path, report)
        archive_report(report_path, report)
        print_progress(f"runner interrupted safely | report={report_path}")
        return 130
    except Exception as error:
        report.update({"status": "failed", "error": str(error)[:4000]})
        write_report(report_path, report)
        archive_report(report_path, report)
        print_progress(f"runner failed | error={str(error)[:500]} | report={report_path}")
        raise


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--endpoint", default="http://127.0.0.1:8765")
    result.add_argument(
        "--data-dir",
        type=Path,
        default=user_data_path("Nerve Center", "TWS"),
        help="Durable local runtime directory outside the checkout.",
    )
    result.add_argument("--report", type=Path)
    result.add_argument("--resume", type=Path)
    result.add_argument("--analyze-resume", action="store_true")
    result.add_argument("--target-title", action="append", default=[])
    result.add_argument("--location", action="append", default=[])
    result.add_argument(
        "--remote-preference",
        choices=("any", "remote", "hybrid", "on_site"),
        default="any",
    )
    result.add_argument("--duration-seconds", type=int, default=1800)
    result.add_argument("--poll-seconds", type=float, default=5.0)
    result.add_argument("--score-limit", type=int, default=10)
    result.add_argument("--model", default="gemma3:4b")
    return result


def main() -> int:
    args = parser().parse_args()
    if args.duration_seconds < 30:
        raise SystemExit("--duration-seconds must be at least 30")
    if args.score_limit < 0:
        raise SystemExit("--score-limit cannot be negative")
    if args.resume is not None and not args.resume.is_file():
        raise SystemExit(f"Resume not found: {args.resume}")
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
