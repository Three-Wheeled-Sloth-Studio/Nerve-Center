import runpy
from pathlib import Path

_SCRIPT = runpy.run_path(
    str(Path(__file__).parents[1] / "scripts" / "run_job_scout_live.py")
)
ProgressReporter = _SCRIPT["ProgressReporter"]
_progress_counts = _SCRIPT["_progress_counts"]


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
