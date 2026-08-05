"""Durable manager-owned work queue contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class WorkClass(StrEnum):
    DETERMINISTIC = "deterministic"
    NETWORK = "network"
    LLM = "llm"
    HUMAN_REVIEW = "human_review"
    COMPOSITE = "composite"


class WorkRequestStatus(StrEnum):
    QUEUED = "queued"
    CLAIMED = "claimed"
    AWAITING_ACKNOWLEDGEMENT = "awaiting_acknowledgement"
    ACKNOWLEDGED = "acknowledged"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        return self in {
            WorkRequestStatus.ACKNOWLEDGED,
            WorkRequestStatus.FAILED,
            WorkRequestStatus.CANCELLED,
        }


class WorkAttemptStatus(StrEnum):
    CLAIMED = "claimed"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    INTERRUPTED = "interrupted"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class WorkRequestSpec:
    module_id: str
    run_id: str
    task_id: str
    work_class: WorkClass
    payload: dict[str, Any]
    idempotency_key: str
    session_id: str | None = None
    provenance: dict[str, Any] = field(default_factory=dict)
    output_contract: dict[str, Any] = field(default_factory=dict)
    requirements: dict[str, Any] = field(default_factory=dict)
    module_priority: int = 10
    task_priority: int = 50
    max_retries: int = 2

    def __post_init__(self) -> None:
        for field_name in ("module_id", "run_id", "task_id", "idempotency_key"):
            if not getattr(self, field_name).strip():
                raise ValueError(f"{field_name} is required")
        if not 0 <= self.module_priority <= 100:
            raise ValueError("module_priority must be between 0 and 100")
        if not 0 <= self.task_priority <= 100:
            raise ValueError("task_priority must be between 0 and 100")
        if self.max_retries < 0:
            raise ValueError("max_retries cannot be negative")


@dataclass(frozen=True, slots=True)
class WorkRequestSnapshot:
    id: str
    module_id: str
    run_id: str
    session_id: str | None
    task_id: str
    work_class: WorkClass
    status: WorkRequestStatus
    payload: dict[str, Any]
    provenance: dict[str, Any]
    output_contract: dict[str, Any]
    requirements: dict[str, Any]
    idempotency_key: str
    module_priority: int
    task_priority: int
    max_retries: int
    attempt_count: int
    available_at: datetime
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    error_code: str | None


@dataclass(frozen=True, slots=True)
class WorkAttemptSnapshot:
    id: str
    request_id: str
    number: int
    status: WorkAttemptStatus
    worker_id: str
    claimed_at: datetime
    completed_at: datetime | None
    error_code: str | None
    detail: dict[str, Any]


@dataclass(frozen=True, slots=True)
class WorkResultSnapshot:
    id: str
    request_id: str
    attempt_id: str
    module_id: str
    payload: dict[str, Any]
    created_at: datetime
    acknowledged_at: datetime | None
    delivery_count: int
    last_delivered_at: datetime | None


@dataclass(frozen=True, slots=True)
class QueueLimits:
    global_soft: int = 100
    global_hard: int = 500
    module_soft: int = 25
    module_hard: int = 100

    def __post_init__(self) -> None:
        if min(self.global_soft, self.global_hard, self.module_soft, self.module_hard) < 1:
            raise ValueError("queue limits must be positive")
        if self.global_soft > self.global_hard or self.module_soft > self.module_hard:
            raise ValueError("soft queue limits cannot exceed hard limits")


@dataclass(frozen=True, slots=True)
class QueueStatusSnapshot:
    module_id: str | None
    queued: int
    claimed: int
    awaiting_acknowledgement: int
    global_queued: int
    soft_limit: int
    hard_limit: int
    pressure: float
    estimated_next_request_wait_seconds: float
    estimated_queue_clear_seconds: float


class WorkRequestNotFoundError(KeyError):
    pass


class WorkAttemptNotFoundError(KeyError):
    pass


class WorkResultNotFoundError(KeyError):
    pass


class QueueLimitExceededError(RuntimeError):
    pass


class WorkQueueConflictError(RuntimeError):
    pass
