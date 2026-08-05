"""Generic async task runner."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

from nerve_center.domain.budget import (
    BudgetExceededError,
    ResourceBudget,
    ResourceBudgetTracker,
    ResourceUsage,
)
from nerve_center.domain.module import ModuleLifecycleState
from nerve_center.domain.run import RunNotReadyError, RunSnapshot, RunStatus
from nerve_center.domain.task import TaskContext, TaskResult, TaskStatus
from nerve_center.persistence.runs import RunRepository
from nerve_center.scheduler.registry import TaskRegistry


class RunnerService:
    def __init__(
        self,
        repository: RunRepository,
        registry: TaskRegistry,
        module_lifecycle: Callable[[str], ModuleLifecycleState] | None = None,
    ) -> None:
        self.repository = repository
        self.registry = registry
        self.module_lifecycle = module_lifecycle
        self._active: dict[str, asyncio.Task[RunSnapshot]] = {}

    def recover_interrupted(self) -> list[RunSnapshot]:
        return self.repository.recover_interrupted()

    async def start(self, run_id: str, now: datetime | None = None) -> RunSnapshot:
        snapshot = self._prepare_start(run_id, now)
        if snapshot.status != RunStatus.RUNNING:
            return snapshot
        if run_id not in self._active:
            task = asyncio.create_task(self._execute(run_id))
            self._active[run_id] = task
            task.add_done_callback(
                lambda _task, identifier=run_id: self._active.pop(identifier, None)
            )
        return snapshot

    async def execute_now(self, run_id: str, now: datetime | None = None) -> RunSnapshot:
        snapshot = self._prepare_start(run_id, now)
        if snapshot.status != RunStatus.RUNNING:
            return snapshot
        return await self._execute(run_id)

    def cancel(self, run_id: str) -> RunSnapshot:
        return self.repository.request_cancel(run_id)

    async def wait(self, run_id: str) -> RunSnapshot:
        task = self._active.get(run_id)
        if task is None:
            return self.repository.get(run_id)
        return await task

    async def shutdown(self, timeout_seconds: float = 5.0) -> None:
        tasks = list(self._active.items())
        for run_id, _task in tasks:
            self.repository.request_cancel(run_id)
        if tasks:
            _done, pending = await asyncio.wait(
                [task for _run_id, task in tasks],
                timeout=timeout_seconds,
            )
            for task in pending:
                task.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)

    def _prepare_start(self, run_id: str, now: datetime | None = None) -> RunSnapshot:
        current = (now or datetime.now(UTC)).astimezone(UTC)
        snapshot = self.repository.get(run_id)
        if snapshot.status.is_terminal:
            return snapshot
        if snapshot.cancel_requested:
            return self.repository.request_cancel(run_id, current)
        module = self.registry.module_for_task(snapshot.task_id)
        if module is not None and self.module_lifecycle is not None:
            lifecycle = self.module_lifecycle(module.module_id)
            if lifecycle != ModuleLifecycleState.ENABLED:
                raise RunNotReadyError(
                    f"module {module.module_id} is {lifecycle.value}"
                )

        if snapshot.window_kind == "duration":
            if snapshot.duration_seconds is None:
                raise ValueError("duration run is missing duration_seconds")
            starts_at = snapshot.starts_at or current
            if snapshot.status == RunStatus.INTERRUPTED and snapshot.deadline is not None:
                if current >= snapshot.deadline:
                    return self.repository.transition(
                        run_id,
                        RunStatus.PARTIAL,
                        now=current,
                        result_summary="The duration deadline passed before the run resumed.",
                    )
                deadline = snapshot.deadline
            else:
                deadline = current + timedelta(seconds=snapshot.duration_seconds)
        else:
            if snapshot.requested_starts_at is None or snapshot.requested_ends_at is None:
                raise ValueError("fixed run is missing requested bounds")
            if current < snapshot.requested_starts_at:
                raise RunNotReadyError(
                    f"run cannot start before {snapshot.requested_starts_at.isoformat()}"
                )
            if current >= snapshot.requested_ends_at:
                target = RunStatus.MISSED if snapshot.starts_at is None else RunStatus.PARTIAL
                return self.repository.transition(
                    run_id,
                    target,
                    now=current,
                    result_summary="The configured run window ended before execution could continue.",
                )
            starts_at = snapshot.starts_at or current
            deadline = snapshot.requested_ends_at

        return self.repository.transition(
            run_id,
            RunStatus.RUNNING,
            now=current,
            starts_at=starts_at,
            deadline=deadline,
        )

    async def _execute(self, run_id: str) -> RunSnapshot:
        snapshot = self.repository.get(run_id)
        if snapshot.starts_at is None or snapshot.deadline is None:
            raise ValueError("running task is missing concrete timing")

        plugin = self.registry.get(snapshot.task_id)
        tracker = ResourceBudgetTracker(
            budget=ResourceBudget(**snapshot.budget),
            usage=ResourceUsage(**snapshot.budget_usage),
            on_change=lambda usage: self.repository.save_budget_usage(run_id, usage),
        )

        def cancellation_requested() -> bool:
            return self.repository.get(run_id).cancel_requested

        def save_checkpoint(value: Mapping[str, Any]) -> None:
            self.repository.save_checkpoint(run_id, dict(value))

        context = TaskContext(
            run_id=run_id,
            started_at=snapshot.starts_at,
            deadline=snapshot.deadline,
            cancellation_requested=cancellation_requested,
            save_checkpoint=save_checkpoint,
            resources=tracker,
            configuration=snapshot.configuration,
            checkpoint=snapshot.checkpoint,
            session_id=snapshot.session_id,
            module_priority=snapshot.module_priority,
        )
        remaining = (snapshot.deadline - datetime.now(UTC)).total_seconds()
        if remaining <= 0:
            return self.repository.transition(
                run_id,
                RunStatus.PARTIAL,
                result_summary="Run deadline was reached before work began.",
            )

        try:
            result = await asyncio.wait_for(plugin.run(context), timeout=remaining)
        except TimeoutError:
            return self.repository.transition(
                run_id,
                RunStatus.PARTIAL,
                result_summary="Run deadline reached; checkpoint preserved.",
                error_code="RUN_DEADLINE_REACHED",
            )
        except BudgetExceededError as error:
            return self.repository.transition(
                run_id,
                RunStatus.PARTIAL,
                result_summary=str(error),
                error_code=f"{error.resource.upper()}_BUDGET_EXHAUSTED",
            )
        except Exception as error:
            return self.repository.transition(
                run_id,
                RunStatus.FAILED,
                result_summary="Task execution failed.",
                error_code=type(error).__name__,
            )

        return self._complete(run_id, result)

    def _complete(self, run_id: str, result: TaskResult) -> RunSnapshot:
        target = {
            TaskStatus.SUCCEEDED: RunStatus.SUCCEEDED,
            TaskStatus.PARTIAL: RunStatus.PARTIAL,
            TaskStatus.CANCELLED: RunStatus.CANCELLED,
            TaskStatus.FAILED: RunStatus.FAILED,
        }[result.status]
        return self.repository.transition(
            run_id,
            target,
            result_summary=result.summary,
            result_metrics=dict(result.metrics),
        )
