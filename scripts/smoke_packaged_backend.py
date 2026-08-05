"""Launch the packaged backend and verify its public health contract."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXECUTABLE = (
    ROOT / "desktop" / "src-tauri" / "resources" / "nerve-center-api.exe"
)
HEALTH_URL = "http://127.0.0.1:8765/health"


def read_health() -> dict[str, object] | None:
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=1) as response:  # noqa: S310
            if response.status != 200:
                return None
            return json.loads(response.read().decode("utf-8"))
    except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError):
        return None


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
    process = subprocess.Popen(  # noqa: S603
        [str(executable)],
        cwd=ROOT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        creationflags=creation_flags,
    )
    deadline = time.monotonic() + args.timeout
    try:
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
                return 0
            time.sleep(0.25)
        raise SystemExit(f"Packaged backend did not become healthy in {args.timeout}s.")
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)


if __name__ == "__main__":
    raise SystemExit(main())
