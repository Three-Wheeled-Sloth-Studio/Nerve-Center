from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from nerve_center.config import Settings
from nerve_center.domain.run import InvalidRunTransitionError, RunStatus
from nerve_center.domain.run_window import DurationRunWindow, FixedRunWindow
from nerve_center.persistence.database import Database
from nerve_center.persistence.runs import RunRepository


def make_repository(tmp_path: Path) -> RunRepository:
    database = Database(Settings(data_dir=tmp_path))
    database.initialize()
    return RunRepository(database)


def test_future_fixed_run_is_scheduled(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    now = datetime(2026, 8, 3, 17, 0, tzinfo=UTC)
    run = repository.create(
        "synthetic",
        FixedRunWindow(now + timedelta(minutes=5), now + timedelta(minutes=15)),
        now=now,
    )

    assert run.status == RunStatus.SCHEDULED


def test_expired_fixed_run_is_missed(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    now = datetime(2026, 8, 3, 17, 0, tzinfo=UTC)
    run = repository.create(
        "synthetic",
        FixedRunWindow(now - timedelta(minutes=10), now - timedelta(minutes=5)),
        now=now,
    )

    assert run.status == RunStatus.MISSED


def test_invalid_transition_is_rejected(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    run = repository.create("synthetic", DurationRunWindow(timedelta(minutes=1)))
    cancelled = repository.request_cancel(run.id)

    with pytest.raises(InvalidRunTransitionError):
        repository.transition(cancelled.id, RunStatus.RUNNING)


def test_cancel_is_idempotent(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    run = repository.create("synthetic", DurationRunWindow(timedelta(minutes=1)))

    first = repository.request_cancel(run.id)
    second = repository.request_cancel(run.id)

    assert first.status == RunStatus.CANCELLED
    assert second.status == RunStatus.CANCELLED
