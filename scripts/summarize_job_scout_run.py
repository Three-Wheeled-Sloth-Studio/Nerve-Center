"""Print a compact, local before/after diagnostic from a live-runner report."""

import argparse
import json
from pathlib import Path

from platformdirs import user_data_path


def summarize(report: dict) -> dict:
    run = report.get("run") or {}
    checkpoint = run.get("checkpoint") or {}
    coverage = checkpoint.get("coverage") or run.get("result_metrics") or {}
    milestones = []
    previous = None
    for entry in report.get("transitions", []):
        state = entry.get("state") or {}
        signature = (
            state.get("wave"), state.get("full_scores"), state.get("reflection"),
            state.get("terminal_reason"),
        )
        if signature != previous:
            milestones.append({"at": entry.get("at"), **state})
            previous = signature
    return {
        "status": report.get("status"), "session": report.get("session"),
        "run": {
            "status": run.get("status"), "summary": run.get("summary"),
            "terminal_reason": checkpoint.get("terminal_reason"),
            "wave": checkpoint.get("wave"), "cycle": checkpoint.get("discovery_cycle"),
            "full_scores": checkpoint.get("full_scores_completed"),
            "provisional_scores": checkpoint.get("provisional_scores_completed"),
            "requests_consumed": checkpoint.get("requests_consumed"),
            "requests_observed": checkpoint.get("requests_observed"),
            "request_batch_overrun": checkpoint.get("request_batch_overrun"),
            "llm_calls_consumed": checkpoint.get("llm_calls_consumed"),
            "coverage": coverage,
        },
        "scoring": report.get("scoring"), "inventory": report.get("inventory"),
        "milestones": milestones,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "report", nargs="?", type=Path,
        default=user_data_path("Nerve Center", "TWS") / "live-tests" / "latest.json",
    )
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    print(json.dumps(summarize(report), indent=2))


if __name__ == "__main__":
    main()
