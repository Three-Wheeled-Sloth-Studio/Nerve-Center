"""Manager-owned summary contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class SummaryCategory(StrEnum):
    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"
    DEGRADED = "degraded"
    COMPARISON = "comparison"
    REVIEW = "review"


@dataclass(frozen=True, slots=True)
class SummaryItem:
    category: SummaryCategory
    source_type: str
    source_id: str
    module_id: str | None
    occurred_at: datetime
    title: str
    summary: str
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SummarySnapshot:
    starts_at: datetime
    ends_at: datetime
    items: tuple[SummaryItem, ...]
    counts: dict[str, int]
