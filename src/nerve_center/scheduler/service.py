"""Polling scheduler for fixed run windows."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from nerve_center.domain.run import RunNotReadyError, RunSnapshot, RunStatus
from nerve_center.persistence.runs import RunRepository
from nerve_center.scheduler.runner import RunnerService


class SchedulerService:
    def __init__(
        self,
        repository: RunRepository,
        runner: RunnerService,
        poll_seconds: float = 1.0,
        session_tick: Callable[[datetime], Awaitable[object]] | None = None,
        queue_tick: Callable[[], Awaitable[object]] | None = None,
    ) -> None:
        self.repository = repository
        self.runner = runner
        self.poll_seconds = poll_seconds
        self.session_tick = session_tick
        self.queue_tick = queue_tick
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._task is None:
            self._stop.clear()
            self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        if self._task is None:
            return
        self._stop.set()
        await self._task
        self._task = None

    async def tick(self, now: datetime | None = None) -> list[RunSnapshot]:
        current = (now or datetime.now(UTC)).astimezone(UTC)
        changed: list[RunSnapshot] = []
        if self.session_tick is not None:
            await self.session_tick(current)
        if self.queue_tick is not None:
            await self.queue_tick()
        for snapshot in self.repository.list_scheduled():
            if snapshot.requested_starts_at is None or snapshot.requested_ends_at is None:
                changed.append(
                    self.repository.transition(
                        snapshot.id,
                        RunStatus.FAILED,
                        now=current,
                        result_summary="Scheduled run is missing fixed window bounds.",
                        error_code="INVALID_SCHEDULED_WINDOW",
                    )
                )
            elif current >= snapshot.requested_ends_at:
                changed.append(
                    self.repository.transition(
                        snapshot.id,
                        RunStatus.MISSED,
                        now=current,
                        result_summary="The full scheduled run window passed before launch.",
                    )
                )
            elif current >= snapshot.requested_starts_at:
                try:
                    changed.append(await self.runner.start(snapshot.id, now=current))
                except RunNotReadyError:
                    # A paused module leaves its scheduled work intact for a later resume.
                    continue
        return changed

    async def _run_loop(self) -> None:
        while not self._stop.is_set():
            await self.tick()
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.poll_seconds)
            except TimeoutError:
                pass
