#!/usr/bin/env python3
"""Fail when distinct tracked Git paths collide after Unicode case folding."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def tracked_paths() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return [item.decode("utf-8") for item in result.stdout.split(b"\0") if item]


def collision_groups(paths: list[str]) -> list[list[str]]:
    groups: dict[str, list[str]] = {}
    for path in paths:
        groups.setdefault(path.casefold(), []).append(path)
    return [sorted(values) for values in groups.values() if len(set(values)) > 1]


def main() -> int:
    try:
        groups = collision_groups(tracked_paths())
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"case-collision check could not read tracked paths: {exc}", file=sys.stderr)
        return 2

    if groups:
        print("tracked-path case-collision check failed:", file=sys.stderr)
        for group in groups:
            print(f"- {' | '.join(group)}", file=sys.stderr)
        return 1

    print("tracked-path case-collision check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
