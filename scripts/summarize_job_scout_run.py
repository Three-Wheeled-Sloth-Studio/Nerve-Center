"""Print a compact, local before/after diagnostic from a live-runner report."""

import argparse
import json
from pathlib import Path

from platformdirs import user_data_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "report", nargs="?", type=Path,
        default=user_data_path("Nerve Center", "TWS") / "live-tests" / "latest.json",
    )
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    print(json.dumps({
        "status": report.get("status"), "session": report.get("session"),
        "run": report.get("run"), "scoring": report.get("scoring"),
        "inventory": report.get("inventory"), "transitions": report.get("transitions", []),
    }, indent=2))


if __name__ == "__main__":
    main()
