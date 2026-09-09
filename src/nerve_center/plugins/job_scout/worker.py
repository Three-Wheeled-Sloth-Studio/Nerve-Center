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
    saved = dict(assignment.get("checkpoint") or {})
    cycle = int(saved.get("discovery_cycle", 0))
    wave = int(saved.get("wave", 1))
    attempted_ids = list(saved.get("scoring_attempted_ids", []))
    full_scores = int(saved.get("full_scores_completed", 0))
    provisional = int(saved.get("provisional_scores_completed", 0))
    idle_rounds = int(saved.get("idle_rounds", 0))
    last_reflection = saved.get("reflection_evidence")
    coverage = dict(saved.get("coverage") or {})
    state = {"value": 0, "activity": "Preparing discovery", "pending_llm": 0}

    async def checkpoint(phase: str, **detail: Any) -> None:
        saved.update(
            discovery_cycle=cycle, wave=wave, phase=phase, coverage=coverage,
            scoring_attempted_ids=attempted_ids,
            full_scores_completed=full_scores,
            provisional_scores_completed=provisional,
            idle_rounds=idle_rounds, reflection_evidence=last_reflection,
            next_work_decision=phase,
        )
        saved.update(detail)
        state["activity"] = f"Wave {wave}: {phase}"
        await client.checkpoint(run_id, saved)

    async def finish(reason: str, status: str = "partial") -> None:
        await checkpoint("stopped", terminal_reason=reason)
        metrics = _completion_metrics(coverage)
        metrics.update(
            wave=wave, cycle=cycle, terminal_reason=reason,
            full_scores_completed=full_scores, provisional_scores_completed=provisional,
        )
        await client.complete(run_id, status, f"Job Scout stopped: {reason}.", metrics)

    async def control_reason(*, check_budgets: bool = True) -> str | None:
        control = await client.control(run_id)
        usage = control.get("budget_usage") or {}
        policy = assignment.get("resource_policy") or {}
        for resource in ("requests", "llm_calls"):
            used = int(usage.get(resource, 0))
            limit = int(policy.get(f"max_{resource}", 500 if resource == "requests" else 100))
            remaining = limit - used
            saved[f"{resource}_consumed"] = used
            saved[f"{resource}_remaining"] = remaining
            if check_budgets and remaining <= 0:
                return f"{resource}_budget_exhausted"
        if control.get("cancel_requested") or control.get("shutdown_requested"):
            return "cancelled"
        if control.get("admission_phase") in {"draining", "closed"}:
            return "admission_" + str(control["admission_phase"])
        if datetime.now(UTC) >= datetime.fromisoformat(str(assignment["deadline"])):
            return "deadline"
        return None

    readiness = await client.invoke(run_id, "discovery_readiness")
    if not readiness.get("ready"):
        await finish("no_configured_evidence_or_market")
        return
    await client.invoke(run_id, "prepare_discovery", {"run_id": run_id})
    await _harvest_reflection_results(client, run_id)
    heartbeat = asyncio.create_task(_heartbeat_while_working(client, state))
    try:
        while True:
            reason = await control_reason()
            if reason:
                await finish(reason, "cancelled" if reason == "cancelled" else "partial")
                return
            cycle += 1
            await checkpoint("expand", idle_reason=None, terminal_reason=None)
            result = await client.invoke(
                run_id, "discovery_cycle", {"run_id": run_id, "cycle": cycle},
            )
            requests = int(result.get("request_count", 0))
            if requests:
                # Source requests are reported at batch completion, not reserved per
                # HTTP fetch. Preserve observed overrun explicitly; never hide it in
                # the manager's capped reservation ledger.
                remaining = int(saved["requests_remaining"])
                saved["requests_observed"] = int(saved.get("requests_observed", 0)) + requests
                saved["request_batch_overrun"] = max(0, requests - remaining)
                await client.consume(run_id, "requests", min(requests, remaining))
                if requests >= remaining:
                    coverage = dict(result.get("coverage") or coverage)
                    await control_reason()
                    await finish("requests_budget_exhausted")
                    return
            coverage = dict(result.get("coverage") or coverage)
            reason = await control_reason()
            if reason:
                await finish(reason, "cancelled" if reason == "cancelled" else "partial")
                return
            await checkpoint("score_candidates")
            scoring = await client.invoke(
                run_id, "scoring_candidates", {"attempted_ids": attempted_ids},
            )
            provisional += int(scoring.get("provisional_scores_completed", 0))
            candidates = scoring.get("candidates") or []
            scored_this_cycle = False
            if candidates and len(attempted_ids) < int(scoring.get("limit", 25)):
                job_id = str(candidates[0])
                attempted_ids.append(job_id)
                # Persist reservation before inference so restart cannot exceed the cap.
                await checkpoint("fit_analysis", scoring_job_id=job_id)
                await client.consume(run_id, "llm_calls")
                scored = await client.invoke(run_id, "score_candidate", {"job_id": job_id})
                full_scores += bool(scored.get("completed"))
                scored_this_cycle = True
                await checkpoint("converge", scoring_outcome=scored)
            else:
                await checkpoint("converge")
            if int(result.get("strategies_attempted", 0)) or scored_this_cycle:
                idle_rounds = 0
            if not result.get("needs_reflection"):
                continue

            # Request new ideation only when durable yield or ranking evidence changes.
            evidence = [
                coverage.get(key, 0) for key in (
                    "companies_discovered", "career_sources_resolved", "opportunities_retained",
                )
            ] + [full_scores]
            reflection = await client.invoke(
                run_id, "deterministic_reflection", {"run_id": run_id, "cycle": cycle},
            )
            added = int(reflection.get("new_strategies", 0))
            if not added and reflection.get("llm_recommended") and evidence != last_reflection:
                reason = await control_reason()
                if reason:
                    await finish(reason, "cancelled" if reason == "cancelled" else "partial")
                    return
                last_reflection = evidence
                request = await client.invoke(
                    run_id, "reflection_work_request", {"run_id": run_id, "cycle": cycle},
                )
                await client.consume(run_id, "llm_calls")
                submitted = await client.submit_work(run_id, request)
                request_id = str(submitted["id"])
                await client.invoke(
                    run_id, "record_reflection_request",
                    {"request_id": request_id, "run_id": run_id, "cycle": cycle},
                )
                await checkpoint("reflect", pending_reflection_request_id=request_id)
                state["pending_llm"] = 1
                for _ in range(180):
                    # The final authorized call must be allowed to return its result.
                    # Exhaustion prevents the next admission, not harvesting this one.
                    reason = await control_reason(check_budgets=False)
                    if reason:
                        await finish(reason, "cancelled" if reason == "cancelled" else "partial")
                        return
                    harvested = await _harvest_reflection_results(client, run_id)
                    if request_id in harvested:
                        added = harvested[request_id]
                        break
                    await asyncio.sleep(5)
                else:
                    await finish("reflection_result_timeout")
                    return
                state["pending_llm"] = 0

            wave += 1
            await checkpoint(
                "refresh", reflection_outcome="added" if added else "no_new_strategies",
                strategies_added=added, pending_reflection_request_id=None,
            )
            # The next cycle reseeds new companies and due sources; eligibility is
            # timestamp-based, so an empty reflection never resets attempt history.
            if result.get("strategies_exhausted") and not added and not scored_this_cycle:
                idle_rounds += 1
                if idle_rounds > 3:
                    await finish("no_work_after_three_refresh_backoffs")
                    return
                seconds = 30 * 2 ** (idle_rounds - 1)
                await checkpoint(
                    "backoff", idle_reason="no_eligible_strategies_or_scoring",
                    backoff_seconds=seconds,
                )
                for _ in range(seconds // 5):
                    reason = await control_reason()
                    if reason:
                        await finish(reason, "cancelled" if reason == "cancelled" else "partial")
                        return
                    await asyncio.sleep(5)
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
