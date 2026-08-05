"""Manager-owned durable work-session repository."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from nerve_center.domain.run_window import ResolvedRunWindow
from nerve_center.domain.session import (
    AdmissionPhase,
    RecurrenceRule,
    SessionStatus,
    WorkSessionSnapshot,
)
from nerve_center.persistence.database import Database
from nerve_center.persistence.models import WorkSessionModel


class SessionNotFoundError(KeyError):
    pass


class SessionRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create(
        self,
        window: ResolvedRunWindow,
        *,
        recurrence: RecurrenceRule | None = None,
        recurrence_parent_id: str | None = None,
        resource_policy: dict[str, int] | None = None,
        now: datetime | None = None,
    ) -> WorkSessionSnapshot:
        current = _utc(now)
        if current >= window.ends_at:
            status = SessionStatus.MISSED
            phase = AdmissionPhase.CLOSED
            finished_at = current
            summary = "The configured session window had already ended."
        elif current < window.starts_at:
            status = SessionStatus.SCHEDULED
            phase = AdmissionPhase.CLOSED
            finished_at = None
            summary = None
        else:
            status = SessionStatus.REQUESTED
            phase = AdmissionPhase.OPEN
            finished_at = None
            summary = None
        model = WorkSessionModel(
            id=str(uuid4()),
            status=status,
            admission_phase=phase,
            starts_at=window.starts_at.astimezone(UTC),
            ends_at=window.ends_at.astimezone(UTC),
            requested_at=current,
            updated_at=current,
            finished_at=finished_at,
            recurrence=recurrence.to_dict() if recurrence else None,
            recurrence_parent_id=recurrence_parent_id,
            module_run_ids={},
            module_priorities={},
            resource_policy=dict(resource_policy or {}),
            emergency_stop=False,
            result_summary=summary,
        )
        with self.database.session() as session:
            session.add(model)
            session.flush()
            return _snapshot(model)

    def get(self, session_id: str) -> WorkSessionSnapshot:
        with self.database.session() as session:
            model = session.get(WorkSessionModel, session_id)
            if model is None:
                raise SessionNotFoundError(f"session {session_id} was not found")
            return _snapshot(model)

    def list_recent(self, limit: int = 100) -> list[WorkSessionSnapshot]:
        with self.database.session() as session:
            models = session.scalars(
                select(WorkSessionModel)
                .order_by(WorkSessionModel.requested_at.desc())
                .limit(limit)
            ).all()
            return [_snapshot(model) for model in models]

    def list_actionable(self) -> list[WorkSessionSnapshot]:
        statuses = {
            SessionStatus.REQUESTED.value,
            SessionStatus.SCHEDULED.value,
            SessionStatus.RUNNING.value,
            SessionStatus.INTERRUPTED.value,
            SessionStatus.DRAINING.value,
        }
        with self.database.session() as session:
            models = session.scalars(
                select(WorkSessionModel)
                .where(WorkSessionModel.status.in_(statuses))
                .order_by(WorkSessionModel.starts_at)
            ).all()
            return [_snapshot(model) for model in models]

    def start(
        self,
        session_id: str,
        module_run_ids: dict[str, str],
        module_priorities: dict[str, int],
        now: datetime | None = None,
    ) -> WorkSessionSnapshot:
        current = _utc(now)
        with self.database.session() as session:
            model = self._model(session, session_id)
            if SessionStatus(model.status).is_terminal:
                return _snapshot(model)
            model.status = SessionStatus.RUNNING
            model.admission_phase = AdmissionPhase.OPEN
            model.module_run_ids = dict(module_run_ids)
            model.module_priorities = dict(module_priorities)
            model.updated_at = current
            session.flush()
            return _snapshot(model)

    def update_phase(
        self,
        session_id: str,
        phase: AdmissionPhase,
        now: datetime | None = None,
    ) -> WorkSessionSnapshot:
        current = _utc(now)
        with self.database.session() as session:
            model = self._model(session, session_id)
            model.admission_phase = phase
            if phase == AdmissionPhase.DRAINING:
                model.status = SessionStatus.DRAINING
            model.updated_at = current
            session.flush()
            return _snapshot(model)

    def finish(
        self,
        session_id: str,
        status: SessionStatus,
        summary: str,
        *,
        emergency_stop: bool = False,
        now: datetime | None = None,
    ) -> WorkSessionSnapshot:
        if not status.is_terminal:
            raise ValueError("session finish requires a terminal status")
        current = _utc(now)
        with self.database.session() as session:
            model = self._model(session, session_id)
            model.status = status
            model.admission_phase = AdmissionPhase.CLOSED
            model.finished_at = current
            model.updated_at = current
            model.emergency_stop = emergency_stop
            model.result_summary = summary
            session.flush()
            return _snapshot(model)

    def recover_interrupted(self, now: datetime | None = None) -> list[WorkSessionSnapshot]:
        current = _utc(now)
        recovered: list[WorkSessionSnapshot] = []
        with self.database.session() as session:
            models = session.scalars(
                select(WorkSessionModel).where(
                    WorkSessionModel.status.in_(
                        [SessionStatus.RUNNING.value, SessionStatus.DRAINING.value]
                    )
                )
            ).all()
            for model in models:
                if current >= _restore_required_utc(model.ends_at):
                    model.status = SessionStatus.COMPLETED
                    model.admission_phase = AdmissionPhase.CLOSED
                    model.finished_at = current
                    model.result_summary = "Session window ended while the manager was offline."
                else:
                    model.status = SessionStatus.INTERRUPTED
                    model.result_summary = "Session was interrupted by a manager restart."
                model.updated_at = current
                recovered.append(_snapshot(model))
            session.flush()
        return recovered

    @staticmethod
    def _model(session: Session, session_id: str) -> WorkSessionModel:
        model = session.get(WorkSessionModel, session_id)
        if model is None:
            raise SessionNotFoundError(f"session {session_id} was not found")
        return model


def _snapshot(model: WorkSessionModel) -> WorkSessionSnapshot:
    recurrence = (
        RecurrenceRule.from_dict(dict(model.recurrence)) if model.recurrence else None
    )
    return WorkSessionSnapshot(
        id=model.id,
        status=SessionStatus(model.status),
        admission_phase=AdmissionPhase(model.admission_phase),
        starts_at=_restore_required_utc(model.starts_at),
        ends_at=_restore_required_utc(model.ends_at),
        requested_at=_restore_required_utc(model.requested_at),
        updated_at=_restore_required_utc(model.updated_at),
        finished_at=_restore_utc(model.finished_at),
        recurrence=recurrence,
        recurrence_parent_id=model.recurrence_parent_id,
        module_run_ids=dict(model.module_run_ids or {}),
        module_priorities={
            key: int(value) for key, value in (model.module_priorities or {}).items()
        },
        resource_policy={
            key: int(value) for key, value in (model.resource_policy or {}).items()
        },
        emergency_stop=model.emergency_stop,
        result_summary=model.result_summary,
    )


def _utc(value: datetime | None) -> datetime:
    current = value or datetime.now(UTC)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("timestamps must be timezone-aware")
    return current.astimezone(UTC)


def _restore_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _restore_required_utc(value: datetime) -> datetime:
    restored = _restore_utc(value)
    if restored is None:
        raise ValueError("required timestamp is missing")
    return restored
