"""Managed child-process entry point for Job Scout work."""

from __future__ import annotations

import asyncio
import os
from contextlib import suppress
from datetime import UTC, datetime
from typing import Any

from nerve_center.runtime.client import ModuleRuntimeClient


async def run_worker() -> None:
    endpoint = _required_environment("NERVE_CENTER_RUNTIME_ENDPOINT")
    token = _required_environment("NERVE_CENTER_RUNTIME_TOKEN")
    module_id = _required_environment("NERVE_CENTER_MODULE_ID")
    client = ModuleRuntimeClient(endpoint, module_id, token)
    try:
        await client.heartbeat("starting", "Job Scout worker started")
        while True:
            if (await client.module_control())["shutdown_requested"]:
                break
            assignment = await client.next_work()
            if assignment is None:
                await client.heartbeat("idle", "Waiting for authorized work")
                await asyncio.sleep(0.5)
                continue
            await _execute_assignment(client, assignment)
    finally:
        with suppress(Exception):
            await client.heartbeat("stopped", "Job Scout worker stopped")
        await client.close()


async def _execute_assignment(
    client: ModuleRuntimeClient, assignment: dict[str, Any]
) -> None:
    run_id = str(assignment["run_id"])
    configuration = assignment.get("configuration") or {}
    checkpoint = assignment.get("checkpoint") or {}
    configured = configuration.get("source_ids")
    if isinstance(configured, list):
        source_ids = [str(item) for item in configured]
    else:
        source_ids = (await client.invoke(run_id, "list_due_sources"))["source_ids"]
    completed = [str(item) for item in checkpoint.get("completed_source_ids", [])]
    remaining = [item for item in source_ids if item not in completed]
    openings_found = 0
    failed_sources = 0
    backlog = {"value": len(remaining), "activity": "Scanning configured job sources"}
    heartbeat = asyncio.create_task(_heartbeat_while_working(client, backlog))
    try:
        for index, source_id in enumerate(remaining):
            backlog["activity"] = f"Scanning source {source_id}"
            control = await client.control(run_id)
            if control["shutdown_requested"] or control["cancel_requested"]:
                await client.complete(
                    run_id,
                    "cancelled",
                    "Job discovery was cancelled.",
                    {"sources_completed": len(completed), "openings_found": openings_found},
                )
                return
            if control["admission_phase"] in {"draining", "closed"}:
                await client.complete(
                    run_id,
                    "partial",
                    "Job discovery stopped during session wind-down.",
                    {"sources_completed": len(completed), "openings_found": openings_found},
                )
                return
            deadline = datetime.fromisoformat(str(assignment["deadline"]))
            if datetime.now(UTC) >= deadline:
                await client.complete(
                    run_id,
                    "partial",
                    "Job discovery reached its run deadline.",
                    {"sources_completed": len(completed), "openings_found": openings_found},
                )
                return
            await client.checkpoint(
                run_id,
                {
                    "completed_source_ids": completed,
                    "active_source_id": source_id,
                    "openings_found": openings_found,
                },
            )
            await client.consume(run_id, "requests")
            result = await client.invoke(run_id, "scan_source", {"source_id": source_id})
            openings_found += int(result["openings_found"])
            if result["status"] not in {"succeeded", "partial"}:
                failed_sources += 1
            completed.append(source_id)
            await client.checkpoint(
                run_id,
                {
                    "completed_source_ids": completed,
                    "active_source_id": None,
                    "last_source_id": source_id,
                    "openings_found": openings_found,
                },
            )
            backlog["value"] = len(remaining) - index - 1
        status = "partial" if failed_sources else "succeeded"
        await client.complete(
            run_id,
            status,
            f"Scanned {len(completed)} sources and found {openings_found} openings.",
            {
                "sources_completed": len(completed),
                "failed_sources": failed_sources,
                "openings_found": openings_found,
            },
        )
    finally:
        heartbeat.cancel()
        await asyncio.gather(heartbeat, return_exceptions=True)


async def _heartbeat_while_working(
    client: ModuleRuntimeClient, state: dict[str, Any]
) -> None:
    while True:
        await client.heartbeat(
            "working",
            str(state["activity"]),
            deterministic_backlog=int(state["value"]),
        )
        await asyncio.sleep(2.0)


def _required_environment(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"required module runtime setting {name} is missing")
    return value


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
