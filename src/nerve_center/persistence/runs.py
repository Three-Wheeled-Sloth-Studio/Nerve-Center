"""Repository for persisted run lifecycle state."""

from __future__ import annotations

from datetime import UTC, datetime
from math import ceil
from typing import Any
from uuid import uuid4

from sqlalchemy import select

from nerve_center.domain.run import (
    ALLOWED_RUN_TRANSITIONS,
    InvalidRunTransitionError,
    RunNotFoundError,
    RunSnapshot,
    RunStatus,
)
from nerve_center.domain.run_window import DurationRunWindow, FixedRunWindow
from nerve_center.persistence.database import Database
from nerve_center.persistence.models import RunEventModel, RunModel


class RunRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create(
        self,
        task_id: str,
        window: DurationRunWindow | FixedRunWindow,
        configuration: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> RunSnapshot:
        current = _utc(now)
        if isinstance(window, DurationRunWindow):
            status = RunStatus.REQUESTED
            window_kind = "duration"
            duration_seconds = max(1, ceil(window.duration.total_seconds()))
            requested_starts_at = None
            requested_ends_at = None
            finished_at = None
            summary = None
        else:
            resolved = window.resolve(current)
            window_kind = "fixed"
            duration_seconds = None
            requested_starts_at = resolved.starts_at
            requested_ends_at = resolved.ends_at
            if current < resolved.starts_at:
                status = RunStatus.SCHEDULED
                finished_at = None
                summary = None
            elif current >= resolved.ends_at:
                status = RunStatus.MISSED
                finished_at = current
                summary = "The configured run window had already ended."
            else:
                status = RunStatus.REQUESTED
                finished_at = None
                summary = None

        model = RunModel(
            id=str(uuid4()),
            task_id=task_id,
            status=status.value,
            window_kind=window_kind,
            duration_seconds=duration_seconds,
            requested_starts_at=requested_starts_at,
            requested_ends_at=requested_ends_at,
            starts_at=None,
            deadline=None,
            requested_at=current,
            updated_at=current,
            finished_at=finished_at,
            cancel_requested=False,
            configuration=dict(configuration or {}),
            checkpoint={},
            result_summary=summary,
            error_code=None,
            result_metrics={},
        )
        with self.database.session() as session:
            session.add(model)
            session.flush()
            session.add(
                RunEventModel(
                    run_id=model.id,
                    created_at=current,
                    event_type="created",
                    source_status=None,
                    target_status=status.value,
                    detail={"window_kind": window_kind},
                )
            )
            return _snapshot(model)

    def get(self, run_id: str) -> RunSnapshot:
        with self.database.session() as session:
            model = session.get(RunModel, run_id)
            if model is None:
                raise RunNotFoundError(f"run {run_id} was not found")
            return _snapshot(model)

    def list_recent(self, limit: int = 100) -> list[RunSnapshot]:
        with self.database.session() as session:
            models = session.scalars(
                select(RunModel).order_by(RunModel.requested_at.desc()).limit(limit)
            ).all()
            return [_snapshot(model) for model in models]

    def transition(
        self,
        run_id: str,
        target: RunStatus,
        *,
        now: datetime | None = None,
        starts_at: datetime | None = None,
        deadline: datetime | None = None,
        result_summary: str | None = None,
        error_code: str | None = None,
        result_metrics: dict[str, int | float | str | bool] | None = None,
    ) -> RunSnapshot:
        current = _utc(now)
        with self.database.session() as session:
            model = session.get(RunModel, run_id)
            if model is None:
                raise RunNotFoundError(f"run {run_id} was not found")
            source = RunStatus(model.status)
            if source == target:
                return _snapshot(model)
            if target not in ALLOWED_RUN_TRANSITIONS[source]:
                raise InvalidRunTransitionError(source, target)

            model.status = target.value
            model.updated_at = current
            if starts_at is not None:
                model.starts_at = _utc(starts_at)
            if deadline is not None:
                model.deadline = _utc(deadline)
            if result_summary is not None:
                model.result_summary = result_summary
            if error_code is not None:
                model.error_code = error_code
            if result_metrics is not None:
                model.result_metrics = dict(result_metrics)
            if target.is_terminal:
                model.finished_at = current

            session.add(
                RunEventModel(
                    run_id=model.id,
                    created_at=current,
                    event_type="transition",
                    source_status=source.value,
                    target_status=target.value,
                    detail={},
                )
            )
            session.flush()
            return _snapshot(model)

    def request_cancel(self, run_id: str, now: datetime | None = None) -> RunSnapshot:
        current = _utc(now)
        with self.database.session() as session:
            model = session.get(RunModel, run_id)
            if model is None:
                raise RunNotFoundError(f"run {run_id} was not found")
            status = RunStatus(model.status)
            if status.is_terminal:
                return _snapshot(model)

            model.cancel_requested = True
            model.updated_at = current
            target = status
            if status in {RunStatus.REQUESTED, RunStatus.SCHEDULED, RunStatus.INTERRUPTED}:
                target = RunStatus.CANCELLED
                model.status = target.value
                model.finished_at = current
                model.result_summary = "Cancelled before execution."
            elif status == RunStatus.RUNNING:
                target = RunStatus.CANCELLING
                model.status = target.value

            if target != status:
                session.add(
                    RunEventModel(
                        run_id=model.id,
                        created_at=current,
                        event_type="cancel_requested",
                        source_status=status.value,
                        target_status=target.value,
                        detail={},
                    )
                )
            session.flush()
            return _snapshot(model)

    def save_checkpoint(self, run_id: str, checkpoint: dict[str, Any]) -> RunSnapshot:
        current = datetime.now(UTC)
        with self.database.session() as session:
            model = session.get(RunModel, run_id)
            if model is None:
                raise RunNotFoundError(f"run {run_id} was not found")
            model.checkpoint = dict(checkpoint)
            model.updated_at = current
            session.add(
                RunEventModel(
                    run_id=model.id,
                    created_at=current,
                    event_type="checkpoint",
                    source_status=model.status,
                    target_status=model.status,
                    detail={"keys": sorted(checkpoint)},
                )
            )
            session.flush()
            return _snapshot(model)

    def recover_interrupted(self, now: datetime | None = None) -> list[RunSnapshot]:
        current = _utc(now)
        recovered: list[RunSnapshot] = []
        with self.database.session() as session:
            models = session.scalars(
                select(RunModel).where(
                    RunModel.status.in_([RunStatus.RUNNING.value, RunStatus.CANCELLING.value])
                )
            ).all()
            for model in models:
                source = RunStatus(model.status)
                model.status = RunStatus.INTERRUPTED.value
                model.updated_at = current
                model.result_summary = "Execution was interrupted by a process restart."
                session.add(
                    RunEventModel(
                        run_id=model.id,
                        created_at=current,
                        event_type="recovered_after_restart",
                        source_status=source.value,
                        target_status=RunStatus.INTERRUPTED.value,
                        detail={},
                    )
                )
                recovered.append(_snapshot(model))
            session.flush()
        return recovered


def _snapshot(model: RunModel) -> RunSnapshot:
    return RunSnapshot(
        id=model.id,
        task_id=model.task_id,
        status=RunStatus(model.status),
        window_kind=model.window_kind,
        duration_seconds=model.duration_seconds,
        requested_starts_at=_restore_utc(model.requested_starts_at),
        requested_ends_at=_restore_utc(model.requested_ends_at),
        starts_at=_restore_utc(model.starts_at),
        deadline=_restore_utc(model.deadline),
        requested_at=_restore_required_utc(model.requested_at),
        updated_at=_restore_required_utc(model.updated_at),
        finished_at=_restore_utc(model.finished_at),
        cancel_requested=model.cancel_requested,
        configuration=dict(model.configuration or {}),
        checkpoint=dict(model.checkpoint or {}),
        result_summary=model.result_summary,
        error_code=model.error_code,
        result_metrics=dict(model.result_metrics or {}),
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
