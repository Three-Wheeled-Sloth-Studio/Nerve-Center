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


async def _execute_assignment(client: ModuleRuntimeClient, assignment: dict[str, Any]) -> None:
    configured = (assignment.get("configuration") or {}).get("source_ids")
    if isinstance(configured, list):
        await _execute_configured_sources(client, assignment, [str(item) for item in configured])
        return
    await _execute_discovery_loop(client, assignment)


async def _execute_discovery_loop(
    client: ModuleRuntimeClient,
    assignment: dict[str, Any],
) -> None:
    run_id = str(assignment["run_id"])
    readiness = await client.invoke(run_id, "discovery_readiness")
    if not bool(readiness.get("ready", False)):
        await client.complete(
            run_id,
            "succeeded",
            "Job Scout has no configured career evidence or durable market sources yet.",
            {
                "sources_completed": 0,
                "strategies_attempted": 0,
                "public_searches_executed": 0,
                "results_examined": 0,
                "companies_discovered": 0,
                "career_sources_resolved": 0,
                "postings_inspected": 0,
                "opportunities_retained": 0,
                "provider_warning_count": 0,
            },
        )
        return

    checkpoint = assignment.get("checkpoint") or {}
    cycle = max(int(checkpoint.get("discovery_cycle", 0)), 0)
    await _harvest_reflection_results(client, run_id)
    prepared = await client.invoke(run_id, "prepare_discovery", {"run_id": run_id})
    state = {
        "value": int(prepared.get("strategies_available", 0)),
        "activity": "Expanding Job Scout market strategies",
        "pending_llm": 0,
    }
    heartbeat = asyncio.create_task(_heartbeat_while_working(client, state))
    try:
        while True:
            control = await client.control(run_id)
            stop_status = _stop_status(control, assignment)
            if stop_status is not None:
                await _complete_from_summary(client, run_id, stop_status)
                return
            cycle += 1
            state["activity"] = f"Job Scout discovery cycle {cycle}"
            await client.checkpoint(
                run_id,
                {
                    "discovery_cycle": cycle,
                    "phase": "expand",
                    "pending_reflection_request_id": None,
                },
            )
            result = await client.invoke(
                run_id,
                "discovery_cycle",
                {"run_id": run_id, "cycle": cycle},
            )
            request_count = int(result.get("request_count", 0))
            if request_count:
                await client.consume(run_id, "requests", request_count)
            coverage = result.get("coverage") or {}
            attempted = int(coverage.get("strategies_attempted", 0))
            state["value"] = max(int(prepared.get("strategies_available", 0)) - attempted, 0)
            await client.checkpoint(
                run_id,
                {
                    "discovery_cycle": cycle,
                    "phase": "reflect" if result.get("needs_reflection") else "converge",
                    "coverage": _checkpoint_coverage(coverage),
                    "pending_reflection_request_id": None,
                },
            )
            if not result.get("needs_reflection"):
                continue
            state["activity"] = "Reflecting on unexplored Job Scout discovery paths"
            reflection = await client.invoke(
                run_id,
                "deterministic_reflection",
                {"run_id": run_id, "cycle": cycle},
            )
            if int(reflection.get("new_strategies", 0)) > 0:
                continue
            if not reflection.get("llm_recommended"):
                await _complete_from_summary(client, run_id, "succeeded")
                return
            control = await client.control(run_id)
            if not bool(control.get("accept_new_llm_work", False)):
                await _complete_from_summary(client, run_id, "partial")
                return
            request = await client.invoke(
                run_id,
                "reflection_work_request",
                {"run_id": run_id, "cycle": cycle},
            )
            await client.consume(run_id, "llm_calls")
            submitted = await client.submit_work(run_id, request)
            request_id = str(submitted["id"])
            await client.invoke(
                run_id,
                "record_reflection_request",
                {"request_id": request_id, "run_id": run_id, "cycle": cycle},
            )
            await client.checkpoint(
                run_id,
                {
                    "discovery_cycle": cycle,
                    "phase": "reflect",
                    "pending_reflection_request_id": request_id,
                    "coverage": _checkpoint_coverage(coverage),
                },
            )
            state["pending_llm"] = 1
            state["activity"] = "Waiting briefly for manager-routed discovery reflection"
            applied = False
            for _ in range(6):
                await asyncio.sleep(0.5)
                harvested = await _harvest_reflection_results(client, run_id)
                if request_id in harvested:
                    applied = harvested[request_id] > 0
                    break
            state["pending_llm"] = 0
            if applied:
                continue
            await _complete_from_summary(client, run_id, "partial", reflection_queued=True)
            return
    finally:
        heartbeat.cancel()
        await asyncio.gather(heartbeat, return_exceptions=True)


async def _harvest_reflection_results(
    client: ModuleRuntimeClient,
    run_id: str,
) -> dict[str, int]:
    harvested: dict[str, int] = {}
    for result in await client.results():
        request_id = str(result.get("request_id", ""))
        payload = result.get("payload") or {}
        value = payload.get("value") if isinstance(payload, dict) else None
        if not request_id or not isinstance(value, dict):
            continue
        applied = await client.invoke(
            run_id,
            "apply_reflection_result",
            {"request_id": request_id, "value": value},
        )
        if not applied.get("recognized"):
            continue
        count = int(applied.get("strategies_added", 0))
        harvested[request_id] = count
        await client.acknowledge_result(
            str(result["id"]),
            accepted=True,
            reason=f"Job Scout accepted {count} new discovery strategies.",
        )
    return harvested


async def _complete_from_summary(
    client: ModuleRuntimeClient,
    run_id: str,
    status: str,
    *,
    reflection_queued: bool = False,
) -> None:
    summary = await client.invoke(run_id, "discovery_summary", {"run_id": run_id})
    metrics = _completion_metrics(summary)
    if reflection_queued:
        metrics["reflection_queued"] = True
    await client.complete(
        run_id,
        status,
        (
            f"Job Scout attempted {metrics['strategies_attempted']} strategies, examined "
            f"{metrics['results_examined']} results, resolved "
            f"{metrics['career_sources_resolved']} career sources, and retained "
            f"{metrics['opportunities_retained']} opportunity observations."
        ),
        metrics,
    )


def _stop_status(control: dict[str, Any], assignment: dict[str, Any]) -> str | None:
    if control["shutdown_requested"] or control["cancel_requested"]:
        return "cancelled"
    if control["admission_phase"] in {"draining", "closed"}:
        return "partial"
    deadline = datetime.fromisoformat(str(assignment["deadline"]))
    if datetime.now(UTC) >= deadline:
        return "partial"
    return None


def _checkpoint_coverage(value: dict[str, Any]) -> dict[str, Any]:
    return {
        key: item
        for key, item in value.items()
        if isinstance(item, (int, float, str, bool))
    }


def _completion_metrics(summary: dict[str, Any]) -> dict[str, int | float | str | bool]:
    metrics: dict[str, int | float | str | bool] = {}
    for key, value in summary.items():
        if isinstance(value, (int, float, str, bool)):
            metrics[key] = value
    warnings = summary.get("provider_warnings", [])
    metrics["provider_warning_count"] = len(warnings) if isinstance(warnings, list) else 0
    return metrics


async def _execute_configured_sources(
    client: ModuleRuntimeClient,
    assignment: dict[str, Any],
    source_ids: list[str],
) -> None:
    run_id = str(assignment["run_id"])
    checkpoint = assignment.get("checkpoint") or {}
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


async def _heartbeat_while_working(client: ModuleRuntimeClient, state: dict[str, Any]) -> None:
    while True:
        await client.heartbeat(
            "waiting_for_llm" if int(state.get("pending_llm", 0)) else "working",
            str(state["activity"]),
            deterministic_backlog=int(state["value"]),
            pending_llm_requests=int(state.get("pending_llm", 0)),
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
