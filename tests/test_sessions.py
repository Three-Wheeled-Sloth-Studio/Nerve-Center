import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

from nerve_center.config import Settings
from nerve_center.domain.run_window import ResolvedRunWindow
from nerve_center.domain.session import (
    AdmissionPhase,
    RecurrenceRule,
    SessionStatus,
    admission_phase_for,
)
from nerve_center.persistence.database import SCHEMA_VERSION, Database
from nerve_center.persistence.modules import ModuleRepository
from nerve_center.persistence.runs import RunRepository
from nerve_center.persistence.sessions import SessionRepository
from nerve_center.plugins.synthetic import SyntheticTaskPlugin
from nerve_center.runtime.supervisor import ModuleSupervisor
from nerve_center.scheduler.registry import TaskRegistry
from nerve_center.scheduler.runner import RunnerService
from nerve_center.scheduler.sessions import WorkSessionService, normalize_priorities


def make_repository(tmp_path: Path) -> SessionRepository:
    database = Database(Settings(data_dir=tmp_path))
    database.initialize()
    return SessionRepository(database)


def test_admission_phase_follows_concrete_wall_clock_window(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    starts_at = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)
    session = repository.create(
        ResolvedRunWindow(starts_at, starts_at + timedelta(hours=10)),
        now=starts_at,
    )

    assert admission_phase_for(session, starts_at + timedelta(hours=1)) == AdmissionPhase.OPEN
    assert (
        admission_phase_for(session, starts_at + timedelta(hours=8))
        == AdmissionPhase.CONSTRAINED
    )
    assert (
        admission_phase_for(session, starts_at + timedelta(hours=9, minutes=30))
        == AdmissionPhase.DRAINING
    )
    assert (
        admission_phase_for(session, starts_at + timedelta(hours=10))
        == AdmissionPhase.CLOSED
    )


def test_queue_estimate_can_advance_admission_phase(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    starts_at = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)
    session = repository.create(
        ResolvedRunWindow(starts_at, starts_at + timedelta(hours=1)),
        now=starts_at,
    )

    assert (
        admission_phase_for(
            session,
            starts_at + timedelta(minutes=10),
            estimated_queue_clear_seconds=55 * 60,
        )
        == AdmissionPhase.DRAINING
    )


def test_recurrence_resolves_local_wall_clock_across_dst() -> None:
    recurrence = RecurrenceRule(
        timezone="America/New_York",
        local_start_time="18:00",
        duration_seconds=14 * 60 * 60,
        weekdays=(0, 1, 2, 3, 4),
    )

    starts_at, ends_at = recurrence.next_window(
        datetime(2026, 10, 30, 23, 0, tzinfo=UTC)
    )

    assert starts_at == datetime(2026, 11, 2, 23, 0, tzinfo=UTC)
    assert ends_at - starts_at == timedelta(hours=14)


def test_restart_preserves_original_session_end(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    starts_at = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)
    created = repository.create(
        ResolvedRunWindow(starts_at, starts_at + timedelta(hours=2)), now=starts_at
    )
    running = repository.start(created.id, {"job_scout": "run-1"}, {"job_scout": 100})

    recovered = repository.recover_interrupted(starts_at + timedelta(hours=1))[0]

    assert running.status == SessionStatus.RUNNING
    assert recovered.status == SessionStatus.INTERRUPTED
    assert recovered.ends_at == starts_at + timedelta(hours=2)
    assert SCHEMA_VERSION == 10


def test_module_priorities_normalize_to_exactly_one_hundred() -> None:
    priorities = normalize_priorities({"alpha": 10, "beta": 10, "gamma": 5})

    assert priorities == {"alpha": 40, "beta": 40, "gamma": 20}
    assert sum(priorities.values()) == 100


def test_missed_recurrence_schedules_next_future_occurrence(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)
    database = Database(settings)
    database.initialize()
    sessions = SessionRepository(database)
    runs = RunRepository(database)
    modules = ModuleRepository(database)
    registry = TaskRegistry()
    registry.register(SyntheticTaskPlugin())
    runner = RunnerService(runs, registry)
    supervisor = ModuleSupervisor(settings)
    service = WorkSessionService(sessions, modules, runs, registry, runner, supervisor)
    starts_at = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)
    recurrence = RecurrenceRule("UTC", "12:00", 3600)
    session = sessions.create(
        ResolvedRunWindow(starts_at, starts_at + timedelta(hours=1)),
        recurrence=recurrence,
        now=starts_at,
    )

    asyncio.run(service.tick(starts_at + timedelta(hours=2)))

    history = sessions.list_recent()
    next_session = next(item for item in history if item.id != session.id)
    assert sessions.get(session.id).status == SessionStatus.MISSED
    assert next_session.recurrence_parent_id == session.id
    assert next_session.starts_at > starts_at + timedelta(hours=2)
