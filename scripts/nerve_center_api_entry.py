"""PyInstaller entry point for the API service and managed module workers."""

import sys

if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--module-worker":
        if sys.argv[2] != "nerve_center.plugins.job_scout.worker":
            raise SystemExit(f"Unsupported module worker: {sys.argv[2]}")
        from nerve_center.plugins.job_scout.worker import main

        main()
    else:
        from nerve_center.api.app import run

        run()
