"""Generic task-plugin contracts."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol

from nerve_center.domain.budget import ResourceBudgetTracker


class TaskStatus(StrEnum):
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class TaskContext:
    run_id: str
    started_at: datetime
    deadline: datetime
    cancellation_requested: Callable[[], bool]
    save_checkpoint: Callable[[Mapping[str, Any]], None]
    resources: ResourceBudgetTracker
    configuration: Mapping[str, Any] = field(default_factory=dict)
    checkpoint: Mapping[str, Any] = field(default_factory=dict)
    session_id: str | None = None
    module_priority: int = 10


@dataclass(frozen=True, slots=True)
class TaskResult:
    status: TaskStatus
    summary: str
    metrics: Mapping[str, int | float | str | bool] = field(default_factory=dict)


class TaskPlugin(Protocol):
    """Reusable task module executed by the Nerve Center runner."""

    plugin_id: str
    display_name: str

    async def run(self, context: TaskContext) -> TaskResult:
        """Execute until complete, cancelled, or the run deadline is reached."""
        ...
