"""Admission, telemetry, and intervention for the durable work queue."""

from __future__ import annotations

from datetime import datetime
from threading import RLock
from typing import Any

from nerve_center.domain.work_queue import (
    QueueLimitExceededError,
    QueueLimits,
    QueueStatusSnapshot,
    WorkAttemptSnapshot,
    WorkClass,
    WorkRequestSnapshot,
    WorkRequestSpec,
    WorkRequestStatus,
    WorkResultSnapshot,
)
from nerve_center.persistence.work_queue import WorkQueueRepository


class WorkQueueService:
    def __init__(
        self,
        repository: WorkQueueRepository,
        *,
        limits: QueueLimits | None = None,
        max_parallel_work: int = 1,
        default_attempt_seconds: float = 30.0,
    ) -> None:
        self.repository = repository
        self.limits = limits or QueueLimits()
        self.max_parallel_work = max(max_parallel_work, 1)
        self.default_attempt_seconds = max(default_attempt_seconds, 0.1)
        self._admission_lock = RLock()

    def submit(
        self, spec: WorkRequestSpec, now: datetime | None = None
    ) -> WorkRequestSnapshot:
        with self._admission_lock:
            duplicate = self.repository.find_by_idempotency(
                spec.module_id, spec.idempotency_key
            )
            if duplicate is not None:
                return duplicate
            module_depth = self.repository.pending_count(spec.module_id)
            global_depth = self.repository.pending_count()
            if module_depth >= self.limits.module_hard:
                raise QueueLimitExceededError(
                    f"module {spec.module_id} reached hard queue limit "
                    f"{self.limits.module_hard}"
                )
            if global_depth >= self.limits.global_hard:
                raise QueueLimitExceededError(
                    f"global hard queue limit {self.limits.global_hard} was reached"
                )
            snapshot, _ = self.repository.submit(spec, now)
            return snapshot

    def get(self, request_id: str) -> WorkRequestSnapshot:
        return self.repository.get(request_id)

    def list_requests(
        self,
        *,
        module_id: str | None = None,
        status: WorkRequestStatus | None = None,
        limit: int = 200,
    ) -> list[WorkRequestSnapshot]:
        return self.repository.list_requests(module_id=module_id, status=status, limit=limit)

    def claim_next(
        self,
        worker_id: str,
        work_classes: tuple[WorkClass, ...] | None = None,
        now: datetime | None = None,
    ) -> WorkAttemptSnapshot | None:
        classes = tuple(item.value for item in work_classes) if work_classes else None
        with self._admission_lock:
            return self.repository.claim_next(worker_id, work_classes=classes, now=now)

    def complete(
        self, attempt_id: str, payload: dict[str, Any], now: datetime | None = None
    ) -> WorkResultSnapshot:
        return self.repository.complete(attempt_id, payload, now)

    def fail(
        self,
        attempt_id: str,
        error_code: str,
        *,
        detail: dict[str, Any] | None = None,
        retry_delay_seconds: float = 0,
        now: datetime | None = None,
    ) -> WorkRequestSnapshot:
        return self.repository.fail(
            attempt_id,
            error_code,
            detail=detail,
            retry_delay_seconds=retry_delay_seconds,
            now=now,
        )

    def attempts(self, request_id: str) -> list[WorkAttemptSnapshot]:
        return self.repository.attempts(request_id)

    def deliver_results(
        self, module_id: str, now: datetime | None = None
    ) -> list[WorkResultSnapshot]:
        return self.repository.deliver_results(module_id, now)

    def acknowledge(
        self, result_id: str, module_id: str, now: datetime | None = None
    ) -> WorkResultSnapshot:
        return self.repository.acknowledge(result_id, module_id, now)

    def cancel(self, request_id: str) -> WorkRequestSnapshot:
        return self.repository.cancel(request_id)

    def retry(self, request_id: str) -> WorkRequestSnapshot:
        return self.repository.retry(request_id)

    def reprioritize(self, request_id: str, task_priority: int) -> WorkRequestSnapshot:
        return self.repository.reprioritize(request_id, task_priority)

    def recover_interrupted(self) -> list[WorkRequestSnapshot]:
        return self.repository.recover_claimed()

    def status(self, module_id: str | None = None) -> QueueStatusSnapshot:
        counts = self.repository.status_counts(module_id)
        global_queued = self.repository.pending_count()
        queued = counts.get(WorkRequestStatus.QUEUED.value, 0)
        claimed = counts.get(WorkRequestStatus.CLAIMED.value, 0)
        awaiting = counts.get(WorkRequestStatus.AWAITING_ACKNOWLEDGEMENT.value, 0)
        depth = queued + claimed + awaiting
        soft = self.limits.module_soft if module_id else self.limits.global_soft
        hard = self.limits.module_hard if module_id else self.limits.global_hard
        average = self.repository.average_attempt_seconds() or self.default_attempt_seconds
        wait = queued * average / self.max_parallel_work
        clear = (queued + claimed) * average / self.max_parallel_work
        return QueueStatusSnapshot(
            module_id=module_id,
            queued=queued,
            claimed=claimed,
            awaiting_acknowledgement=awaiting,
            global_queued=global_queued,
            soft_limit=soft,
            hard_limit=hard,
            pressure=min(depth / hard, 1.0),
            estimated_next_request_wait_seconds=wait,
            estimated_queue_clear_seconds=clear,
        )
