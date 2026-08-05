"""Manager work-session orchestration and wall-clock admission control."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from nerve_center.domain.budget import ResourceBudget
from nerve_center.domain.module import ModuleLifecycleState
from nerve_center.domain.run_window import DurationRunWindow, FixedRunWindow, ResolvedRunWindow
from nerve_center.domain.session import (
    AdmissionPhase,
    RecurrenceRule,
    SessionStatus,
    WorkSessionSnapshot,
    admission_phase_for,
)
from nerve_center.persistence.modules import ModuleRepository
from nerve_center.persistence.runs import RunRepository
from nerve_center.persistence.sessions import SessionRepository
from nerve_center.runtime.supervisor import ModuleSupervisor
from nerve_center.scheduler.registry import TaskRegistry
from nerve_center.scheduler.runner import RunnerService


class WorkSessionService:
    def __init__(
        self,
        sessions: SessionRepository,
        modules: ModuleRepository,
        runs: RunRepository,
        registry: TaskRegistry,
        runner: RunnerService,
        supervisor: ModuleSupervisor,
    ) -> None:
        self.sessions = sessions
        self.modules = modules
        self.runs = runs
        self.registry = registry
        self.runner = runner
        self.supervisor = supervisor

    def create_duration(
        self,
        duration_seconds: int,
        *,
        resource_policy: dict[str, int] | None = None,
        now: datetime | None = None,
    ) -> WorkSessionSnapshot:
        current = _utc(now)
        window = DurationRunWindow(timedelta(seconds=duration_seconds)).resolve(current)
        return self.sessions.create(window, resource_policy=resource_policy, now=current)

    def create_fixed(
        self,
        starts_at: datetime,
        ends_at: datetime,
        *,
        resource_policy: dict[str, int] | None = None,
        now: datetime | None = None,
    ) -> WorkSessionSnapshot:
        current = _utc(now)
        window = FixedRunWindow(starts_at, ends_at).resolve(current)
        return self.sessions.create(window, resource_policy=resource_policy, now=current)

    def create_recurring(
        self,
        recurrence: RecurrenceRule,
        *,
        resource_policy: dict[str, int] | None = None,
        now: datetime | None = None,
    ) -> WorkSessionSnapshot:
        current = _utc(now)
        starts_at, ends_at = recurrence.next_window(current)
        return self.sessions.create(
            ResolvedRunWindow(starts_at, ends_at),
            recurrence=recurrence,
            resource_policy=resource_policy,
            now=current,
        )

    async def start(
        self, session_id: str, now: datetime | None = None
    ) -> WorkSessionSnapshot:
        current = _utc(now)
        snapshot = self.sessions.get(session_id)
        if snapshot.status.is_terminal:
            return snapshot
        if current < snapshot.starts_at:
            return snapshot
        if current >= snapshot.ends_at:
            return self._finish_occurrence(
                snapshot,
                SessionStatus.MISSED,
                "The full session window passed before launch.",
                current,
            )

        run_ids = dict(snapshot.module_run_ids)
        priorities = dict(snapshot.module_priorities)
        if not run_ids:
            enabled = [
                module
                for module in self.modules.list()
                if module.lifecycle_state == ModuleLifecycleState.ENABLED
                and module.manifest.session_entry_task_id is not None
            ]
            if not enabled:
                return self._finish_occurrence(
                    snapshot,
                    SessionStatus.FAILED,
                    "No enabled module has a session entry task.",
                    current,
                )
            priorities = normalize_priorities(
                {item.manifest.module_id: item.saved_priority for item in enabled}
            )
            budget = _resource_budget(snapshot.resource_policy)
            for module in enabled:
                task_id = module.manifest.session_entry_task_id
                if task_id is None:
                    continue
                self.registry.get(task_id)
                run = self.runs.create(
                    task_id,
                    FixedRunWindow(snapshot.starts_at, snapshot.ends_at),
                    budget=budget,
                    now=current,
                    session_id=snapshot.id,
                    module_priority=priorities[module.manifest.module_id],
                )
                run_ids[module.manifest.module_id] = run.id
        running = self.sessions.start(snapshot.id, run_ids, priorities, now=current)
        await asyncio.gather(
            *(self.runner.start(run_id, now=current) for run_id in run_ids.values())
        )
        return running

    async def tick(self, now: datetime | None = None) -> list[WorkSessionSnapshot]:
        current = _utc(now)
        changed: list[WorkSessionSnapshot] = []
        for snapshot in self.sessions.list_actionable():
            if current >= snapshot.ends_at:
                if not snapshot.module_run_ids:
                    changed.append(
                        self._finish_occurrence(
                            snapshot,
                            SessionStatus.MISSED,
                            "The session window passed before work started.",
                            current,
                        )
                    )
                else:
                    changed.append(await self._close(snapshot, current))
                continue
            if snapshot.status in {
                SessionStatus.REQUESTED,
                SessionStatus.SCHEDULED,
                SessionStatus.INTERRUPTED,
            } and current >= snapshot.starts_at:
                snapshot = await self.start(snapshot.id, current)
                changed.append(snapshot)
            if snapshot.status in {SessionStatus.RUNNING, SessionStatus.DRAINING}:
                phase = admission_phase_for(
                    snapshot,
                    current,
                    self._estimated_queue_clear(snapshot),
                )
                if phase != snapshot.admission_phase:
                    snapshot = self.sessions.update_phase(snapshot.id, phase, current)
                    changed.append(snapshot)
        return changed

    def recover(self, now: datetime | None = None) -> list[WorkSessionSnapshot]:
        current = _utc(now)
        recovered = self.sessions.recover_interrupted(current)
        for snapshot in recovered:
            if snapshot.status == SessionStatus.COMPLETED and snapshot.recurrence is not None:
                self._schedule_next(snapshot, current)
        return recovered

    async def emergency_stop(
        self, session_id: str, now: datetime | None = None
    ) -> WorkSessionSnapshot:
        current = _utc(now)
        snapshot = self.sessions.get(session_id)
        if snapshot.status.is_terminal:
            return snapshot
        for run_id in snapshot.module_run_ids.values():
            self.runner.cancel(run_id)
        await asyncio.gather(
            *(self.supervisor.stop(module_id, 1.0) for module_id in snapshot.module_run_ids)
        )
        return self.sessions.finish(
            session_id,
            SessionStatus.CANCELLED,
            "Emergency Stop ended the session and terminated module workers.",
            emergency_stop=True,
            now=current,
        )

    def control(self, session_id: str) -> dict[str, float | str | bool]:
        snapshot = self.sessions.get(session_id)
        now = datetime.now(UTC)
        queue_clear = self._estimated_queue_clear(snapshot)
        phase = admission_phase_for(
            snapshot,
            now,
            queue_clear,
        )
        waits = [
            self.supervisor.report(module_id).estimated_next_request_wait_seconds or 0.0
            for module_id in snapshot.module_run_ids
        ]
        return {
            "admission_phase": phase.value,
            "remaining_seconds": max((snapshot.ends_at - now).total_seconds(), 0.0),
            "estimated_queue_clear_seconds": queue_clear,
            "estimated_next_request_wait_seconds": max(waits, default=0.0),
            "accept_new_llm_work": phase in {AdmissionPhase.OPEN, AdmissionPhase.CONSTRAINED},
        }

    async def _close(
        self, snapshot: WorkSessionSnapshot, now: datetime
    ) -> WorkSessionSnapshot:
        self.sessions.update_phase(snapshot.id, AdmissionPhase.CLOSED, now)
        for run_id in snapshot.module_run_ids.values():
            current_run = self.runs.get(run_id)
            if not current_run.status.is_terminal:
                self.runner.cancel(run_id)
        await asyncio.gather(
            *(self.supervisor.stop(module_id) for module_id in snapshot.module_run_ids)
        )
        return self._finish_occurrence(
            snapshot,
            SessionStatus.COMPLETED,
            "The authorized wall-clock session ended.",
            now,
        )

    def _finish_occurrence(
        self,
        snapshot: WorkSessionSnapshot,
        status: SessionStatus,
        summary: str,
        now: datetime,
    ) -> WorkSessionSnapshot:
        finished = self.sessions.finish(snapshot.id, status, summary, now=now)
        if snapshot.recurrence is not None:
            self._schedule_next(snapshot, now)
        return finished

    def _schedule_next(self, snapshot: WorkSessionSnapshot, after: datetime) -> None:
        if snapshot.recurrence is None:
            return
        starts_at, ends_at = snapshot.recurrence.next_window(after)
        self.sessions.create(
            ResolvedRunWindow(starts_at, ends_at),
            recurrence=snapshot.recurrence,
            recurrence_parent_id=snapshot.id,
            resource_policy=snapshot.resource_policy,
            now=after,
        )

    def _estimated_queue_clear(self, snapshot: WorkSessionSnapshot) -> float:
        estimates = [
            self.supervisor.report(module_id).estimated_queue_clear_seconds or 0.0
            for module_id in snapshot.module_run_ids
        ]
        return max(estimates, default=0.0)


def normalize_priorities(weights: dict[str, int]) -> dict[str, int]:
    if not weights:
        return {}
    positive = {key: max(value, 0) for key, value in weights.items()}
    total = sum(positive.values())
    if total == 0:
        positive = dict.fromkeys(positive, 1)
        total = len(positive)
    exact = {key: value * 100 / total for key, value in positive.items()}
    allocated = {key: int(value) for key, value in exact.items()}
    remainder = 100 - sum(allocated.values())
    order = sorted(exact, key=lambda key: (-(exact[key] - allocated[key]), key))
    for key in order[:remainder]:
        allocated[key] += 1
    return allocated


def _resource_budget(policy: dict[str, int]) -> ResourceBudget:
    defaults = ResourceBudget()
    return ResourceBudget(
        max_requests=int(policy.get("max_requests", defaults.max_requests)),
        max_llm_calls=int(policy.get("max_llm_calls", defaults.max_llm_calls)),
        max_parallel_work=int(policy.get("max_parallel_work", defaults.max_parallel_work)),
    )


def _utc(value: datetime | None) -> datetime:
    current = value or datetime.now(UTC)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("timestamps must be timezone-aware")
    return current.astimezone(UTC)
