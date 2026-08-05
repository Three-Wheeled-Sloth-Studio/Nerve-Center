"""SQLite persistence for durable manager work delivery."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from nerve_center.domain.work_queue import (
    WorkAttemptNotFoundError,
    WorkAttemptSnapshot,
    WorkAttemptStatus,
    WorkClass,
    WorkQueueConflictError,
    WorkRequestNotFoundError,
    WorkRequestSnapshot,
    WorkRequestSpec,
    WorkRequestStatus,
    WorkResultNotFoundError,
    WorkResultSnapshot,
)
from nerve_center.persistence.database import Database
from nerve_center.persistence.models import (
    WorkAttemptModel,
    WorkRequestModel,
    WorkResultModel,
)

PENDING_STATUSES = (
    WorkRequestStatus.QUEUED.value,
    WorkRequestStatus.CLAIMED.value,
    WorkRequestStatus.AWAITING_ACKNOWLEDGEMENT.value,
)


class WorkQueueRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def submit(
        self, spec: WorkRequestSpec, now: datetime | None = None
    ) -> tuple[WorkRequestSnapshot, bool]:
        current = _utc(now)
        with self.database.session() as session:
            existing = session.scalar(
                select(WorkRequestModel).where(
                    WorkRequestModel.module_id == spec.module_id,
                    WorkRequestModel.idempotency_key == spec.idempotency_key,
                )
            )
            if existing is not None:
                return _request_snapshot(existing), False
            model = WorkRequestModel(
                id=str(uuid4()),
                module_id=spec.module_id,
                run_id=spec.run_id,
                session_id=spec.session_id,
                task_id=spec.task_id,
                work_class=spec.work_class.value,
                status=WorkRequestStatus.QUEUED.value,
                payload=dict(spec.payload),
                provenance=dict(spec.provenance),
                output_contract=dict(spec.output_contract),
                requirements=dict(spec.requirements),
                idempotency_key=spec.idempotency_key,
                module_priority=spec.module_priority,
                task_priority=spec.task_priority,
                max_retries=spec.max_retries,
                attempt_count=0,
                available_at=current,
                created_at=current,
                updated_at=current,
                completed_at=None,
                error_code=None,
            )
            session.add(model)
            session.flush()
            return _request_snapshot(model), True

    def get(self, request_id: str) -> WorkRequestSnapshot:
        with self.database.session() as session:
            return _request_snapshot(self._request(session, request_id))

    def find_by_idempotency(
        self, module_id: str, idempotency_key: str
    ) -> WorkRequestSnapshot | None:
        with self.database.session() as session:
            model = session.scalar(
                select(WorkRequestModel).where(
                    WorkRequestModel.module_id == module_id,
                    WorkRequestModel.idempotency_key == idempotency_key,
                )
            )
            return _request_snapshot(model) if model is not None else None

    def list_requests(
        self,
        *,
        module_id: str | None = None,
        status: WorkRequestStatus | None = None,
        limit: int = 200,
    ) -> list[WorkRequestSnapshot]:
        statement = select(WorkRequestModel)
        if module_id is not None:
            statement = statement.where(WorkRequestModel.module_id == module_id)
        if status is not None:
            statement = statement.where(WorkRequestModel.status == status.value)
        statement = statement.order_by(WorkRequestModel.created_at.desc()).limit(limit)
        with self.database.session() as session:
            return [_request_snapshot(item) for item in session.scalars(statement).all()]

    def pending_count(self, module_id: str | None = None) -> int:
        statement = select(func.count()).select_from(WorkRequestModel).where(
            WorkRequestModel.status.in_(PENDING_STATUSES)
        )
        if module_id is not None:
            statement = statement.where(WorkRequestModel.module_id == module_id)
        with self.database.session() as session:
            return int(session.scalar(statement) or 0)

    def status_counts(self, module_id: str | None = None) -> dict[str, int]:
        statement = select(WorkRequestModel.status, func.count()).group_by(
            WorkRequestModel.status
        )
        if module_id is not None:
            statement = statement.where(WorkRequestModel.module_id == module_id)
        with self.database.session() as session:
            return {str(status): int(count) for status, count in session.execute(statement)}

    def average_attempt_seconds(self) -> float | None:
        with self.database.session() as session:
            attempts = session.scalars(
                select(WorkAttemptModel).where(WorkAttemptModel.completed_at.is_not(None))
            ).all()
            durations = [
                (_required_utc(item.completed_at) - _required_utc(item.claimed_at)).total_seconds()
                for item in attempts
                if item.completed_at is not None
            ]
            return sum(durations) / len(durations) if durations else None

    def claim_next(
        self,
        worker_id: str,
        *,
        work_classes: tuple[str, ...] | None = None,
        now: datetime | None = None,
    ) -> WorkAttemptSnapshot | None:
        current = _utc(now)
        with self.database.session() as session:
            statement = select(WorkRequestModel).where(
                WorkRequestModel.status == WorkRequestStatus.QUEUED.value,
                WorkRequestModel.available_at <= current,
            )
            if work_classes:
                statement = statement.where(WorkRequestModel.work_class.in_(work_classes))
            request = session.scalar(
                statement.order_by(
                    WorkRequestModel.module_priority.desc(),
                    WorkRequestModel.task_priority.desc(),
                    WorkRequestModel.created_at.asc(),
                ).limit(1)
            )
            if request is None:
                return None
            request.attempt_count += 1
            request.status = WorkRequestStatus.CLAIMED.value
            request.updated_at = current
            attempt = WorkAttemptModel(
                id=str(uuid4()),
                request_id=request.id,
                number=request.attempt_count,
                status=WorkAttemptStatus.CLAIMED.value,
                worker_id=worker_id,
                claimed_at=current,
                completed_at=None,
                error_code=None,
                detail={},
            )
            session.add(attempt)
            session.flush()
            return _attempt_snapshot(attempt)

    def complete(
        self,
        attempt_id: str,
        payload: dict[str, Any],
        now: datetime | None = None,
    ) -> WorkResultSnapshot:
        current = _utc(now)
        with self.database.session() as session:
            attempt = self._attempt(session, attempt_id)
            request = self._request(session, attempt.request_id)
            if WorkAttemptStatus(attempt.status) != WorkAttemptStatus.CLAIMED:
                raise WorkQueueConflictError(f"attempt {attempt_id} is already complete")
            attempt.status = WorkAttemptStatus.SUCCEEDED.value
            attempt.completed_at = current
            request.status = WorkRequestStatus.AWAITING_ACKNOWLEDGEMENT.value
            request.updated_at = current
            request.completed_at = current
            result = WorkResultModel(
                id=str(uuid4()),
                request_id=request.id,
                attempt_id=attempt.id,
                module_id=request.module_id,
                payload=dict(payload),
                created_at=current,
                acknowledged_at=None,
                delivery_count=0,
                last_delivered_at=None,
            )
            session.add(result)
            session.flush()
            return _result_snapshot(result)

    def fail(
        self,
        attempt_id: str,
        error_code: str,
        *,
        detail: dict[str, Any] | None = None,
        retry_delay_seconds: float = 0,
        now: datetime | None = None,
    ) -> WorkRequestSnapshot:
        current = _utc(now)
        with self.database.session() as session:
            attempt = self._attempt(session, attempt_id)
            request = self._request(session, attempt.request_id)
            if WorkAttemptStatus(attempt.status) != WorkAttemptStatus.CLAIMED:
                raise WorkQueueConflictError(f"attempt {attempt_id} is already complete")
            attempt.status = WorkAttemptStatus.FAILED.value
            attempt.completed_at = current
            attempt.error_code = error_code
            attempt.detail = dict(detail or {})
            request.error_code = error_code
            request.updated_at = current
            if request.attempt_count <= request.max_retries:
                request.status = WorkRequestStatus.QUEUED.value
                request.available_at = current + timedelta(seconds=max(retry_delay_seconds, 0))
            else:
                request.status = WorkRequestStatus.FAILED.value
                request.completed_at = current
            session.flush()
            return _request_snapshot(request)

    def attempts(self, request_id: str) -> list[WorkAttemptSnapshot]:
        self.get(request_id)
        with self.database.session() as session:
            items = session.scalars(
                select(WorkAttemptModel)
                .where(WorkAttemptModel.request_id == request_id)
                .order_by(WorkAttemptModel.number)
            ).all()
            return [_attempt_snapshot(item) for item in items]

    def deliver_results(
        self, module_id: str, now: datetime | None = None
    ) -> list[WorkResultSnapshot]:
        current = _utc(now)
        with self.database.session() as session:
            items = session.scalars(
                select(WorkResultModel)
                .where(
                    WorkResultModel.module_id == module_id,
                    WorkResultModel.acknowledged_at.is_(None),
                )
                .order_by(WorkResultModel.created_at)
            ).all()
            for item in items:
                item.delivery_count += 1
                item.last_delivered_at = current
            session.flush()
            return [_result_snapshot(item) for item in items]

    def acknowledge(
        self, result_id: str, module_id: str, now: datetime | None = None
    ) -> WorkResultSnapshot:
        current = _utc(now)
        with self.database.session() as session:
            result = session.get(WorkResultModel, result_id)
            if result is None:
                raise WorkResultNotFoundError(f"result {result_id} was not found")
            if result.module_id != module_id:
                raise WorkQueueConflictError("result belongs to a different module")
            if result.acknowledged_at is None:
                result.acknowledged_at = current
                request = self._request(session, result.request_id)
                request.status = WorkRequestStatus.ACKNOWLEDGED.value
                request.updated_at = current
            session.flush()
            return _result_snapshot(result)

    def cancel(self, request_id: str, now: datetime | None = None) -> WorkRequestSnapshot:
        current = _utc(now)
        with self.database.session() as session:
            request = self._request(session, request_id)
            if not WorkRequestStatus(request.status).is_terminal:
                if request.status == WorkRequestStatus.CLAIMED.value:
                    attempt = session.scalar(
                        select(WorkAttemptModel).where(
                            WorkAttemptModel.request_id == request.id,
                            WorkAttemptModel.status == WorkAttemptStatus.CLAIMED.value,
                        )
                    )
                    if attempt is not None:
                        attempt.status = WorkAttemptStatus.CANCELLED.value
                        attempt.completed_at = current
                        attempt.error_code = "cancelled"
                request.status = WorkRequestStatus.CANCELLED.value
                request.updated_at = current
                request.completed_at = current
            session.flush()
            return _request_snapshot(request)

    def recover_claimed(self, now: datetime | None = None) -> list[WorkRequestSnapshot]:
        current = _utc(now)
        recovered: list[WorkRequestSnapshot] = []
        with self.database.session() as session:
            requests = session.scalars(
                select(WorkRequestModel).where(
                    WorkRequestModel.status == WorkRequestStatus.CLAIMED.value
                )
            ).all()
            for request in requests:
                attempt = session.scalar(
                    select(WorkAttemptModel).where(
                        WorkAttemptModel.request_id == request.id,
                        WorkAttemptModel.status == WorkAttemptStatus.CLAIMED.value,
                    )
                )
                if attempt is not None:
                    attempt.status = WorkAttemptStatus.INTERRUPTED.value
                    attempt.completed_at = current
                    attempt.error_code = "manager_restart"
                    attempt.detail = {"reason": "manager restart before completion"}
                request.status = WorkRequestStatus.QUEUED.value
                request.available_at = current
                request.updated_at = current
                request.error_code = "manager_restart"
                recovered.append(_request_snapshot(request))
            session.flush()
        return recovered

    def retry(self, request_id: str, now: datetime | None = None) -> WorkRequestSnapshot:
        current = _utc(now)
        with self.database.session() as session:
            request = self._request(session, request_id)
            if request.status not in {
                WorkRequestStatus.FAILED.value,
                WorkRequestStatus.CANCELLED.value,
            }:
                raise WorkQueueConflictError("only failed or cancelled work can be retried")
            request.status = WorkRequestStatus.QUEUED.value
            request.available_at = current
            request.updated_at = current
            request.completed_at = None
            request.error_code = None
            session.flush()
            return _request_snapshot(request)

    def reprioritize(
        self, request_id: str, task_priority: int, now: datetime | None = None
    ) -> WorkRequestSnapshot:
        if not 0 <= task_priority <= 100:
            raise ValueError("task_priority must be between 0 and 100")
        current = _utc(now)
        with self.database.session() as session:
            request = self._request(session, request_id)
            if request.status != WorkRequestStatus.QUEUED.value:
                raise WorkQueueConflictError("only queued work can be reprioritized")
            request.task_priority = task_priority
            request.updated_at = current
            session.flush()
            return _request_snapshot(request)

    @staticmethod
    def _request(session: Session, request_id: str) -> WorkRequestModel:
        model = session.get(WorkRequestModel, request_id)
        if model is None:
            raise WorkRequestNotFoundError(f"work request {request_id} was not found")
        return model

    @staticmethod
    def _attempt(session: Session, attempt_id: str) -> WorkAttemptModel:
        model = session.get(WorkAttemptModel, attempt_id)
        if model is None:
            raise WorkAttemptNotFoundError(f"work attempt {attempt_id} was not found")
        return model


def _request_snapshot(model: WorkRequestModel) -> WorkRequestSnapshot:
    return WorkRequestSnapshot(
        id=model.id,
        module_id=model.module_id,
        run_id=model.run_id,
        session_id=model.session_id,
        task_id=model.task_id,
        work_class=WorkClass(model.work_class),
        status=WorkRequestStatus(model.status),
        payload=dict(model.payload),
        provenance=dict(model.provenance or {}),
        output_contract=dict(model.output_contract or {}),
        requirements=dict(model.requirements or {}),
        idempotency_key=model.idempotency_key,
        module_priority=model.module_priority,
        task_priority=model.task_priority,
        max_retries=model.max_retries,
        attempt_count=model.attempt_count,
        available_at=_required_utc(model.available_at),
        created_at=_required_utc(model.created_at),
        updated_at=_required_utc(model.updated_at),
        completed_at=_restore_utc(model.completed_at),
        error_code=model.error_code,
    )


def _attempt_snapshot(model: WorkAttemptModel) -> WorkAttemptSnapshot:
    return WorkAttemptSnapshot(
        id=model.id,
        request_id=model.request_id,
        number=model.number,
        status=WorkAttemptStatus(model.status),
        worker_id=model.worker_id,
        claimed_at=_required_utc(model.claimed_at),
        completed_at=_restore_utc(model.completed_at),
        error_code=model.error_code,
        detail=dict(model.detail or {}),
    )


def _result_snapshot(model: WorkResultModel) -> WorkResultSnapshot:
    return WorkResultSnapshot(
        id=model.id,
        request_id=model.request_id,
        attempt_id=model.attempt_id,
        module_id=model.module_id,
        payload=dict(model.payload),
        created_at=_required_utc(model.created_at),
        acknowledged_at=_restore_utc(model.acknowledged_at),
        delivery_count=model.delivery_count,
        last_delivered_at=_restore_utc(model.last_delivered_at),
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


def _required_utc(value: datetime | None) -> datetime:
    restored = _restore_utc(value)
    if restored is None:
        raise ValueError("required timestamp is missing")
    return restored
