import runpy
from pathlib import Path

_SCRIPT = runpy.run_path(
    str(Path(__file__).parents[1] / "scripts" / "summarize_job_scout_run.py")
)


def test_summary_keeps_wave_scoring_reflection_and_stop_milestones():
    report = {
        "status": "completed",
        "run": {"status": "partial", "checkpoint": {
            "wave": 2, "discovery_cycle": 4, "full_scores_completed": 1,
            "terminal_reason": "requests_budget_exhausted",
            "coverage": {"opportunities_retained": 8},
        }},
        "transitions": [
            {"at": "1", "state": {"wave": 1, "cycle": 1, "full_scores": 0}},
            {"at": "2", "state": {"wave": 1, "cycle": 2, "full_scores": 0}},
            {"at": "3", "state": {"wave": 1, "cycle": 2, "full_scores": 1}},
            {"at": "4", "state": {"wave": 2, "cycle": 3, "full_scores": 1,
                                     "reflection": "no_new_strategies"}},
        ],
    }
    summary = _SCRIPT["summarize"](report)
    assert summary["run"]["coverage"]["opportunities_retained"] == 8
    assert [item["at"] for item in summary["milestones"]] == ["1", "3", "4"]
