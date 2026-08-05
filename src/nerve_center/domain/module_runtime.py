"""Versioned manager-to-module runtime contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

MODULE_RUNTIME_API_VERSION = 1


class ModuleRuntimeStatus(StrEnum):
    STARTING = "starting"
    WORKING = "working"
    IDLE = "idle"
    THROTTLED = "throttled"
    WAITING_FOR_LLM = "waiting_for_llm"
    WAITING_FOR_HUMAN = "waiting_for_human"
    STOPPING = "stopping"
    STOPPED = "stopped"
    DEGRADED = "degraded"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ModuleRuntimeReport:
    module_id: str
    status: ModuleRuntimeStatus
    activity: str
    process_id: int | None = None
    last_heartbeat_at: datetime | None = None
    work_items_processed: int = 0
    deterministic_backlog: int = 0
    pending_llm_requests: int = 0
    estimated_next_request_wait_seconds: float | None = None
    estimated_queue_clear_seconds: float | None = None
    queue_pressure: float = 0.0
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ModuleRunAssignment:
    runtime_api_version: int
    module_id: str
    module_version: str
    run_id: str
    task_id: str
    deadline: datetime
    priority: int
    queue_limits: dict[str, int]
    resource_policy: dict[str, int]
    data_directory: str
    configuration: dict[str, Any] = field(default_factory=dict)
    checkpoint: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
