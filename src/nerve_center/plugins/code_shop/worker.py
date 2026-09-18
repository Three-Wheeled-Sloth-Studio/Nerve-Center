"""Managed child-process entry point for Code Shop orchestration work."""

from __future__ import annotations

import asyncio
import os
from contextlib import suppress
from typing import Any

from nerve_center.runtime.client import ModuleRuntimeClient


async def run_worker() -> None:
    client = ModuleRuntimeClient(
        _required_environment("NERVE_CENTER_RUNTIME_ENDPOINT"),
        _required_environment("NERVE_CENTER_MODULE_ID"),
        _required_environment("NERVE_CENTER_RUNTIME_TOKEN"),
    )
    try:
        await client.heartbeat("starting", "Code Shop worker started")
        while True:
            if (await client.module_control())["shutdown_requested"]:
                break
            assignment = await client.next_work()
            if assignment is None:
                await client.heartbeat("idle", "Waiting for authorized engineering work")
                await asyncio.sleep(0.5)
                continue
            await _execute_assignment(client, assignment)
    finally:
        with suppress(Exception):
            await client.heartbeat("stopped", "Code Shop worker stopped")
        await client.close()


async def _execute_assignment(
    client: ModuleRuntimeClient,
    assignment: dict[str, Any],
) -> None:
    run_id = str(assignment["run_id"])
    configuration = dict(assignment.get("configuration") or {})
    if "model" in configuration or "provider" in configuration:
        await client.complete(
            run_id,
            "failed",
            "Code Shop rejected a non-model-blind capability request.",
            {"error": "model_selection_not_allowed"},
        )
        return
    try:
        task = await client.invoke(run_id, "submit_capability", configuration)
    except Exception:
        await client.complete(
            run_id,
            "failed",
            "Code Shop could not create the requested engineering task.",
            {"error": "capability_submission_failed"},
        )
        return
    await client.complete(
        run_id,
        "succeeded",
        f"Code Shop queued engineering task {task['id']}.",
        {
            "task_id": str(task["id"]),
            "capability": str(task["capability"]),
        },
    )


def _required_environment(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"required module runtime setting {name} is missing")
    return value


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
