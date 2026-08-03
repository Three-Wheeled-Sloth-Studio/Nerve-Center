import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

from nerve_center.config import Settings
from nerve_center.domain.budget import ResourceBudget
from nerve_center.domain.run import RunStatus
from nerve_center.domain.run_window import DurationRunWindow
from nerve_center.persistence.database import Database
from nerve_center.persistence.runs import RunRepository
from nerve_center.plugins.synthetic import SyntheticTaskPlugin
from nerve_center.scheduler.registry import TaskRegistry
from nerve_center.scheduler.runner import RunnerService


def make_runner(tmp_path: Path) -> tuple[RunRepository, RunnerService]:
    database = Database(Settings(data_dir=tmp_path))
    database.initialize()
    repository = RunRepository(database)
    registry = TaskRegistry()
    registry.register(SyntheticTaskPlugin())
    return repository, RunnerService(repository, registry)


def test_runner_completes_and_checkpoints(tmp_path: Path) -> None:
    repository, runner = make_runner(tmp_path)
    run = repository.create(
        "synthetic",
        DurationRunWindow(timedelta(seconds=5)),
        configuration={"iterations": 3},
    )

    result = asyncio.run(runner.execute_now(run.id))

    assert result.status == RunStatus.SUCCEEDED
    assert result.checkpoint == {"completed": 3}
    assert result.result_metrics["completed"] == 3


def test_restart_recovery_marks_running_run_interrupted(tmp_path: Path) -> None:
    repository, runner = make_runner(tmp_path)
    run = repository.create("synthetic", DurationRunWindow(timedelta(seconds=5)))
    repository.transition(
        run.id,
        RunStatus.RUNNING,
        starts_at=datetime.now(UTC),
        deadline=datetime.now(UTC) + timedelta(seconds=5),
    )

    recovered = runner.recover_interrupted()

    assert recovered[0].status == RunStatus.INTERRUPTED
    assert repository.get(run.id).status == RunStatus.INTERRUPTED


def test_cancel_before_execution_is_terminal(tmp_path: Path) -> None:
    repository, runner = make_runner(tmp_path)
    run = repository.create("synthetic", DurationRunWindow(timedelta(seconds=5)))

    cancelled = runner.cancel(run.id)
    result = asyncio.run(runner.execute_now(run.id))

    assert cancelled.status == RunStatus.CANCELLED
    assert result.status == RunStatus.CANCELLED


def test_runner_stops_when_request_budget_is_exhausted(tmp_path: Path) -> None:
    repository, runner = make_runner(tmp_path)
    run = repository.create(
        "synthetic",
        DurationRunWindow(timedelta(seconds=5)),
        configuration={"iterations": 3, "requests_per_iteration": 1},
        budget=ResourceBudget(max_requests=2),
    )

    result = asyncio.run(runner.execute_now(run.id))

    assert result.status == RunStatus.PARTIAL
    assert result.error_code == "REQUESTS_BUDGET_EXHAUSTED"
    assert result.budget_usage["requests"] == 2
