import runpy
from pathlib import Path

_SCRIPT = runpy.run_path(
    str(Path(__file__).parents[1] / "scripts" / "run_job_scout_live.py")
)
ProgressReporter = _SCRIPT["ProgressReporter"]
_progress_counts = _SCRIPT["_progress_counts"]
_remaining_session_seconds = _SCRIPT["_remaining_session_seconds"]
_resumable_job_scout_session = _SCRIPT["_resumable_job_scout_session"]


def test_progress_counts_are_ordered_and_limited_to_known_metrics() -> None:
    assert _progress_counts(
        {
            "opportunities_retained": 7,
            "strategies_attempted": 12,
            "results_examined": 40,
            "private_detail": 99,
        }
    ) == (("strategies", 12), ("results", 40), ("roles", 7))


def test_reporter_emits_transitions_and_periodic_heartbeat(capsys) -> None:
    now = [100.0]
    reporter = ProgressReporter(heartbeat_seconds=60, clock=lambda: now[0])
    run = {
        "status": "running",
        "checkpoint": {
            "phase": "expand",
            "discovery_cycle": 3,
            "coverage": {
                "strategies_attempted": 8,
                "companies_discovered": 4,
                "opportunities_retained": 6,
            },
        },
    }

    assert reporter.observe_run(run) == (
        "discovery expand cycle=3 | strategies=8 | companies=4 | roles=6"
    )
    now[0] = 130.0
    assert reporter.observe_run(run) is None
    now[0] = 160.0
    assert reporter.observe_run(run) == (
        "heartbeat | discovery expand cycle=3 | strategies=8 | companies=4 | roles=6"
    )
    run["checkpoint"]["phase"] = "reflect"
    assert reporter.observe_run(run) == (
        "discovery reflect cycle=3 | strategies=8 | companies=4 | roles=6"
    )

    output = capsys.readouterr().out
    assert output.count("discovery expand cycle=3") == 2
    assert "discovery reflect cycle=3" in output


def test_manager_queue_changes_emit_immediately() -> None:
    now = [100.0]
    reporter = ProgressReporter(heartbeat_seconds=60, clock=lambda: now[0])
    session = {"status": "draining", "admission_phase": "draining"}

    assert reporter.observe_manager(session, {"queued": 1, "claimed": 0}) == (
        "manager draining | queued=1 | claimed=0"
    )
    assert reporter.observe_manager(session, {"queued": 0, "claimed": 1}) == (
        "manager draining | queued=0 | claimed=1"
    )


def test_resumable_session_requires_an_actionable_job_scout_run() -> None:
    selected = _resumable_job_scout_session(
        [
            {"id": "failed", "status": "failed", "module_run_ids": {}},
            {
                "id": "active",
                "status": "interrupted",
                "module_run_ids": {"job_scout": "run-1"},
            },
            {
                "id": "other",
                "status": "running",
                "module_run_ids": {"another_module": "run-2"},
            },
        ]
    )

    assert selected is not None
    assert selected["id"] == "active"


def test_remaining_session_seconds_uses_fallback_for_invalid_deadline() -> None:
    assert _remaining_session_seconds({"ends_at": "not-a-date"}, 300) == 300.0


def test_monitor_returns_scored_terminal_run_without_waiting_for_open_manager(
    tmp_path, monkeypatch,
):
    monitor = _SCRIPT["monitor_session"]
    calls = []

    def request(endpoint, path, method="GET", payload=None):
        calls.append(path)
        if path.startswith("/api/v1/sessions?"):
            return [{"id": "session", "status": "running",
                     "module_run_ids": {"job_scout": "run"}}]
        if path == "/api/v1/runs/run":
            return {"status": "partial", "checkpoint": {
                "full_scores_completed": 1, "terminal_reason": "no_work",
            }}
        raise AssertionError(f"Unexpected wait after scoring: {path}")

    monkeypatch.setitem(monitor.__globals__, "request_json", request)
    report = {}
    final, _ = monitor("http://fixture", 28800, 5, tmp_path / "report.json", report)
    assert final["checkpoint"]["full_scores_completed"] == 1
    assert calls == ["/api/v1/sessions?limit=20", "/api/v1/runs/run"]


def test_monitor_submits_explicit_resource_policy(tmp_path, monkeypatch):
    monitor = _SCRIPT["monitor_session"]
    submitted = []

    def request(endpoint, path, method="GET", payload=None):
        if path.startswith("/api/v1/sessions?"):
            return []
        if path == "/api/v1/sessions":
            submitted.append(payload)
            return {
                "id": "session",
                "status": "running",
                "ends_at": None,
                "module_run_ids": {"job_scout": "run"},
                "resource_policy": payload["resource_policy"],
            }
        if path == "/api/v1/runs/run":
            return {
                "status": "partial",
                "checkpoint": {"terminal_reason": "requests_budget_exhausted"},
            }
        raise AssertionError(path)

    monkeypatch.setitem(monitor.__globals__, "request_json", request)
    report = {}
    monitor(
        "http://fixture",
        1800,
        0,
        tmp_path / "report.json",
        report,
        max_requests=1200,
        max_llm_calls=75,
    )

    assert submitted == [{
        "duration_seconds": 1800,
        "resource_policy": {"max_requests": 1200, "max_llm_calls": 75},
    }]
    assert report["session"]["resource_policy"] == {
        "max_requests": 1200,
        "max_llm_calls": 75,
    }
