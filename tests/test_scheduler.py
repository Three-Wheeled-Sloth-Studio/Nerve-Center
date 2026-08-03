import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

from nerve_center.config import Settings
from nerve_center.domain.run import RunStatus
from nerve_center.domain.run_window import FixedRunWindow
from nerve_center.persistence.database import Database
from nerve_center.persistence.runs import RunRepository
from nerve_center.plugins.synthetic import SyntheticTaskPlugin
from nerve_center.scheduler.registry import TaskRegistry
from nerve_center.scheduler.runner import RunnerService
from nerve_center.scheduler.service import SchedulerService


def make_scheduler(tmp_path: Path) -> tuple[RunRepository, RunnerService, SchedulerService]:
    database = Database(Settings(data_dir=tmp_path))
    database.initialize()
    repository = RunRepository(database)
    registry = TaskRegistry()
    registry.register(SyntheticTaskPlugin())
    runner = RunnerService(repository, registry)
    return repository, runner, SchedulerService(repository, runner)


def test_tick_starts_due_fixed_run(tmp_path: Path) -> None:
    repository, runner, scheduler = make_scheduler(tmp_path)
    now = datetime.now(UTC)
    run = repository.create(
        "synthetic",
        FixedRunWindow(now + timedelta(seconds=1), now + timedelta(seconds=30)),
        configuration={"iterations": 0},
        now=now,
    )

    async def execute() -> RunStatus:
        await scheduler.tick(now + timedelta(seconds=2))
        result = await runner.wait(run.id)
        return result.status

    assert asyncio.run(execute()) == RunStatus.SUCCEEDED


def test_tick_marks_expired_window_missed(tmp_path: Path) -> None:
    repository, _runner, scheduler = make_scheduler(tmp_path)
    now = datetime.now(UTC)
    run = repository.create(
        "synthetic",
        FixedRunWindow(now + timedelta(seconds=1), now + timedelta(seconds=2)),
        now=now,
    )

    asyncio.run(scheduler.tick(now + timedelta(seconds=3)))

    assert repository.get(run.id).status == RunStatus.MISSED
