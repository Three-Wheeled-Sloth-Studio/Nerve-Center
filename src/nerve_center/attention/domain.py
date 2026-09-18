"""Generic manager-owned human-attention contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any


class AttentionKind(StrEnum):
    ATTENTION = "attention"
    REVIEW = "review"


class AttentionState(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


@dataclass(frozen=True, slots=True)
class AttentionItem:
    id: str
    kind: AttentionKind
    module_id: str
    source_type: str
    source_id: str
    idempotency_key: str
    title: str
    summary: str
    context: dict[str, Any]
    allowed_dispositions: tuple[str, ...]
    validation: dict[str, Any]
    downstream_meaning: dict[str, Any]
    dependency_keys: tuple[str, ...]
    state: AttentionState
    resolution: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None


@dataclass(frozen=True, slots=True)
class AttentionEvent:
    id: int
    item_id: str
    event_type: str
    detail: dict[str, Any]
    created_at: datetime
