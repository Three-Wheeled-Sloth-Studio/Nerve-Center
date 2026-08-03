"""Persisted run lifecycle contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class RunStatus(StrEnum):
    REQUESTED = "requested"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    CANCELLING = "cancelling"
    INTERRUPTED = "interrupted"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    FAILED = "failed"
    MISSED = "missed"

    @property
    def is_terminal(self) -> bool:
        return self in TERMINAL_RUN_STATUSES


TERMINAL_RUN_STATUSES = frozenset(
    {
        RunStatus.SUCCEEDED,
        RunStatus.PARTIAL,
        RunStatus.CANCELLED,
        RunStatus.FAILED,
        RunStatus.MISSED,
    }
)

ALLOWED_RUN_TRANSITIONS: dict[RunStatus, frozenset[RunStatus]] = {
    RunStatus.REQUESTED: frozenset(
        {RunStatus.SCHEDULED, RunStatus.RUNNING, RunStatus.CANCELLED, RunStatus.MISSED}
    ),
    RunStatus.SCHEDULED: frozenset(
        {RunStatus.RUNNING, RunStatus.CANCELLED, RunStatus.MISSED}
    ),
    RunStatus.RUNNING: frozenset(
        {
            RunStatus.CANCELLING,
            RunStatus.INTERRUPTED,
            RunStatus.SUCCEEDED,
            RunStatus.PARTIAL,
            RunStatus.CANCELLED,
            RunStatus.FAILED,
        }
    ),
    RunStatus.CANCELLING: frozenset(
        {RunStatus.INTERRUPTED, RunStatus.CANCELLED, RunStatus.PARTIAL, RunStatus.FAILED}
    ),
    RunStatus.INTERRUPTED: frozenset(
        {RunStatus.RUNNING, RunStatus.CANCELLED, RunStatus.PARTIAL, RunStatus.MISSED}
    ),
    RunStatus.SUCCEEDED: frozenset(),
    RunStatus.PARTIAL: frozenset(),
    RunStatus.CANCELLED: frozenset(),
    RunStatus.FAILED: frozenset(),
    RunStatus.MISSED: frozenset(),
}


class RunError(RuntimeError):
    """Base error for run lifecycle operations."""


class RunNotFoundError(RunError):
    pass


class RunNotReadyError(RunError):
    pass


class InvalidRunTransitionError(RunError):
    def __init__(self, source: RunStatus, target: RunStatus) -> None:
        super().__init__(f"run cannot transition from {source.value} to {target.value}")
        self.source = source
        self.target = target


@dataclass(frozen=True, slots=True)
class RunSnapshot:
    id: str
    task_id: str
    status: RunStatus
    window_kind: str
    duration_seconds: int | None
    requested_starts_at: datetime | None
    requested_ends_at: datetime | None
    starts_at: datetime | None
    deadline: datetime | None
    requested_at: datetime
    updated_at: datetime
    finished_at: datetime | None
    cancel_requested: bool
    configuration: dict[str, Any] = field(default_factory=dict)
    checkpoint: dict[str, Any] = field(default_factory=dict)
    result_summary: str | None = None
    error_code: str | None = None
    result_metrics: dict[str, int | float | str | bool] = field(default_factory=dict)
