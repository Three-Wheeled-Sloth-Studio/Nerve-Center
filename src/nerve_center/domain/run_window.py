"""Run-window contracts for duration and fixed-time execution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol


class RunWindow(Protocol):
    """A user-configured execution window that can be resolved to concrete timestamps."""

    def resolve(self, now: datetime) -> ResolvedRunWindow:
        """Resolve this configuration into a concrete execution interval."""


@dataclass(frozen=True, slots=True)
class ResolvedRunWindow:
    """Concrete inclusive-start, exclusive-end execution interval."""

    starts_at: datetime
    ends_at: datetime

    def __post_init__(self) -> None:
        _require_aware(self.starts_at, "starts_at")
        _require_aware(self.ends_at, "ends_at")
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be later than starts_at")

    def contains(self, moment: datetime) -> bool:
        _require_aware(moment, "moment")
        return self.starts_at <= moment < self.ends_at

    def can_start_new_work(self, moment: datetime) -> bool:
        return self.contains(moment)

    def remaining(self, moment: datetime) -> timedelta:
        _require_aware(moment, "moment")
        if moment >= self.ends_at:
            return timedelta(0)
        return self.ends_at - max(moment, self.starts_at)


@dataclass(frozen=True, slots=True)
class DurationRunWindow:
    """Window beginning when the run starts and lasting for a configured duration."""

    duration: timedelta

    def __post_init__(self) -> None:
        if self.duration <= timedelta(0):
            raise ValueError("duration must be positive")

    def resolve(self, now: datetime) -> ResolvedRunWindow:
        _require_aware(now, "now")
        return ResolvedRunWindow(starts_at=now, ends_at=now + self.duration)


@dataclass(frozen=True, slots=True)
class FixedRunWindow:
    """Window with explicit timezone-aware start and end timestamps."""

    starts_at: datetime
    ends_at: datetime

    def resolve(self, now: datetime) -> ResolvedRunWindow:
        _require_aware(now, "now")
        return ResolvedRunWindow(starts_at=self.starts_at, ends_at=self.ends_at)


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
