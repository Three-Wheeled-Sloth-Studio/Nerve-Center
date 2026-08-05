"""Build the self-contained Windows backend used by the Tauri package."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTRY_POINT = ROOT / "scripts" / "nerve_center_api_entry.py"
DIST_DIR = ROOT / "desktop" / "src-tauri" / "resources"
WORK_DIR = ROOT / "build" / "pyinstaller"
OUTPUT = DIST_DIR / "nerve-center-api.exe"


def build_command() -> list[str]:
    return [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--console",
        "--name",
        "nerve-center-api",
        "--distpath",
        str(DIST_DIR),
        "--workpath",
        str(WORK_DIR),
        "--specpath",
        str(WORK_DIR),
        "--paths",
        str(ROOT / "src"),
        "--collect-submodules",
        "uvicorn",
        "--collect-submodules",
        "pydantic",
        "--collect-submodules",
        "sqlalchemy",
        str(ENTRY_POINT),
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print and validate the packaging command without invoking PyInstaller.",
    )
    args = parser.parse_args()

    if not ENTRY_POINT.is_file():
        raise SystemExit(f"Packaging entry point is missing: {ENTRY_POINT}")

    command = build_command()
    if args.dry_run:
        print(subprocess.list2cmdline(command))
        return 0

    if os.name != "nt":
        raise SystemExit("The Windows backend must be built on Windows.")

    DIST_DIR.mkdir(parents=True, exist_ok=True)
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    if OUTPUT.exists():
        OUTPUT.unlink()
    stale_spec = WORK_DIR / "nerve-center-api.spec"
    if stale_spec.exists():
        stale_spec.unlink()

    completed = subprocess.run(command, cwd=ROOT, check=False)
    if completed.returncode != 0:
        return completed.returncode
    if not OUTPUT.is_file():
        raise SystemExit(f"PyInstaller completed without producing {OUTPUT}")

    size_mb = OUTPUT.stat().st_size / (1024 * 1024)
    print(f"Built {OUTPUT} ({size_mb:.1f} MiB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
