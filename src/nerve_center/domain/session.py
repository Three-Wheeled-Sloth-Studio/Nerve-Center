"""Durable manager work-session contracts and admission policy."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from enum import StrEnum
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class SessionStatus(StrEnum):
    REQUESTED = "requested"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    INTERRUPTED = "interrupted"
    DRAINING = "draining"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    MISSED = "missed"
    FAILED = "failed"

    @property
    def is_terminal(self) -> bool:
        return self in {
            SessionStatus.COMPLETED,
            SessionStatus.CANCELLED,
            SessionStatus.MISSED,
            SessionStatus.FAILED,
        }


class AdmissionPhase(StrEnum):
    OPEN = "open"
    CONSTRAINED = "constrained"
    DRAINING = "draining"
    CLOSED = "closed"


@dataclass(frozen=True, slots=True)
class RecurrenceRule:
    timezone: str
    local_start_time: str
    duration_seconds: int
    weekdays: tuple[int, ...] = (0, 1, 2, 3, 4, 5, 6)

    def __post_init__(self) -> None:
        _ = self.zone
        _ = self.start_time
        if self.duration_seconds < 1:
            raise ValueError("recurring duration must be positive")
        if not self.weekdays or any(day < 0 or day > 6 for day in self.weekdays):
            raise ValueError("recurring weekdays must contain values from 0 through 6")

    @property
    def zone(self) -> ZoneInfo:
        try:
            return ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as error:
            raise ValueError(f"unknown recurrence timezone {self.timezone!r}") from error

    @property
    def start_time(self) -> time:
        try:
            return time.fromisoformat(self.local_start_time)
        except ValueError as error:
            raise ValueError("local_start_time must use HH:MM[:SS] format") from error

    def next_window(self, after: datetime) -> tuple[datetime, datetime]:
        _require_aware(after, "after")
        local_after = after.astimezone(self.zone)
        for offset in range(8):
            candidate_date: date = local_after.date() + timedelta(days=offset)
            if candidate_date.weekday() not in self.weekdays:
                continue
            candidate = datetime.combine(candidate_date, self.start_time, self.zone)
            if candidate <= local_after:
                continue
            starts_at = candidate.astimezone(UTC)
            return starts_at, starts_at + timedelta(seconds=self.duration_seconds)
        raise ValueError("recurrence does not produce a window in the next week")

    def to_dict(self) -> dict[str, Any]:
        return {
            "timezone": self.timezone,
            "local_start_time": self.local_start_time,
            "duration_seconds": self.duration_seconds,
            "weekdays": list(self.weekdays),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> RecurrenceRule:
        return cls(
            timezone=str(value["timezone"]),
            local_start_time=str(value["local_start_time"]),
            duration_seconds=int(value["duration_seconds"]),
            weekdays=tuple(int(day) for day in value.get("weekdays", range(7))),
        )


@dataclass(frozen=True, slots=True)
class WorkSessionSnapshot:
    id: str
    status: SessionStatus
    admission_phase: AdmissionPhase
    starts_at: datetime
    ends_at: datetime
    requested_at: datetime
    updated_at: datetime
    finished_at: datetime | None
    recurrence: RecurrenceRule | None = None
    recurrence_parent_id: str | None = None
    module_run_ids: dict[str, str] = field(default_factory=dict)
    module_priorities: dict[str, int] = field(default_factory=dict)
    resource_policy: dict[str, int] = field(default_factory=dict)
    emergency_stop: bool = False
    result_summary: str | None = None

    @property
    def duration(self) -> timedelta:
        return self.ends_at - self.starts_at


def admission_phase_for(
    session: WorkSessionSnapshot,
    now: datetime,
    estimated_queue_clear_seconds: float = 0.0,
) -> AdmissionPhase:
    _require_aware(now, "now")
    current = now.astimezone(UTC)
    if current >= session.ends_at or session.status.is_terminal:
        return AdmissionPhase.CLOSED
    if current < session.starts_at:
        return AdmissionPhase.CLOSED
    remaining = (session.ends_at - current).total_seconds()
    total = max(session.duration.total_seconds(), 1.0)
    fraction_remaining = remaining / total
    if estimated_queue_clear_seconds >= remaining:
        return AdmissionPhase.DRAINING
    if fraction_remaining <= 0.1:
        return AdmissionPhase.DRAINING
    if fraction_remaining <= 0.3 or estimated_queue_clear_seconds >= remaining * 0.7:
        return AdmissionPhase.CONSTRAINED
    return AdmissionPhase.OPEN


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
