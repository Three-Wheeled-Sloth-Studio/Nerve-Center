"""API request and response schemas."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Any, Self

from pydantic import BaseModel, Field, model_validator

from nerve_center.domain.budget import ResourceBudget
from nerve_center.domain.module import InstalledModule, ModuleLifecycleState
from nerve_center.domain.module_runtime import ModuleRuntimeReport
from nerve_center.domain.run import RunEventSnapshot, RunSnapshot, RunStatus
from nerve_center.domain.run_window import DurationRunWindow, FixedRunWindow
from nerve_center.domain.session import RecurrenceRule, WorkSessionSnapshot
from nerve_center.domain.work_queue import (
    QueueStatusSnapshot,
    WorkAttemptSnapshot,
    WorkClass,
    WorkRequestSnapshot,
    WorkRequestSpec,
    WorkRequestStatus,
    WorkResultSnapshot,
)
from nerve_center.profile.models import ClaimCategory, ClaimDecision, HypothesisDecision


class ResourceBudgetRequest(BaseModel):
    max_requests: int = Field(default=500, ge=1)
    max_llm_calls: int = Field(default=100, ge=1)
    max_parallel_work: int = Field(default=3, ge=1, le=100)

    def to_domain(self) -> ResourceBudget:
        return ResourceBudget(**self.model_dump())


class RunCreateRequest(BaseModel):
    task_id: str = Field(min_length=1, max_length=100)
    duration_seconds: int | None = Field(default=None, ge=1)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    configuration: dict[str, Any] = Field(default_factory=dict)
    budget: ResourceBudgetRequest = Field(default_factory=ResourceBudgetRequest)

    @model_validator(mode="after")
    def validate_window(self) -> Self:
        has_duration = self.duration_seconds is not None
        has_fixed = self.starts_at is not None or self.ends_at is not None
        if has_duration == has_fixed:
            raise ValueError("provide either duration_seconds or both starts_at and ends_at")
        if has_fixed and (self.starts_at is None or self.ends_at is None):
            raise ValueError("both starts_at and ends_at are required for a fixed window")
        return self

    def to_window(self) -> DurationRunWindow | FixedRunWindow:
        if self.duration_seconds is not None:
            return DurationRunWindow(timedelta(seconds=self.duration_seconds))
        if self.starts_at is None or self.ends_at is None:
            raise ValueError("fixed window is incomplete")
        return FixedRunWindow(self.starts_at, self.ends_at)


class RunResponse(BaseModel):
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
    configuration: dict[str, Any]
    checkpoint: dict[str, Any]
    budget: dict[str, int]
    budget_usage: dict[str, int]
    result_summary: str | None
    error_code: str | None
    result_metrics: dict[str, int | float | str | bool]
    session_id: str | None
    module_priority: int

    @classmethod
    def from_snapshot(cls, snapshot: RunSnapshot) -> RunResponse:
        values = asdict(snapshot)
        if not values["result_summary"]:
            active_source = snapshot.checkpoint.get("active_source_id")
            last_source = snapshot.checkpoint.get("last_source_id")
            if active_source:
                values["result_summary"] = f"Scanning source {active_source}."
            elif last_source and snapshot.finished_at is None:
                values["result_summary"] = f"Last completed source {last_source}."
        return cls(**values)


class RunEventResponse(BaseModel):
    id: int
    run_id: str
    created_at: datetime
    event_type: str
    source_status: str | None
    target_status: str | None
    detail: dict[str, Any]

    @classmethod
    def from_snapshot(cls, snapshot: RunEventSnapshot) -> RunEventResponse:
        return cls(**asdict(snapshot))


class ModuleLifecycleRequest(BaseModel):
    lifecycle_state: ModuleLifecycleState


class ModuleResponse(BaseModel):
    manifest: dict[str, Any]
    lifecycle_state: ModuleLifecycleState
    saved_priority: int
    runtime: dict[str, Any] | None = None

    @classmethod
    def from_installed(
        cls,
        installed: InstalledModule,
        runtime: ModuleRuntimeReport | None = None,
    ) -> ModuleResponse:
        return cls(
            manifest=installed.manifest.to_dict(),
            lifecycle_state=installed.lifecycle_state,
            saved_priority=installed.saved_priority,
            runtime=runtime.to_dict() if runtime else None,
        )


class SessionCreateRequest(BaseModel):
    duration_seconds: int | None = Field(default=None, ge=1)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    recurrence_timezone: str | None = None
    recurrence_local_start_time: str | None = None
    recurrence_duration_seconds: int | None = Field(default=None, ge=1)
    recurrence_weekdays: list[int] = Field(default_factory=lambda: list(range(7)))
    resource_policy: ResourceBudgetRequest = Field(default_factory=ResourceBudgetRequest)

    @model_validator(mode="after")
    def validate_mode(self) -> Self:
        duration = self.duration_seconds is not None
        fixed = self.starts_at is not None or self.ends_at is not None
        recurring = any(
            value is not None
            for value in (
                self.recurrence_timezone,
                self.recurrence_local_start_time,
                self.recurrence_duration_seconds,
            )
        )
        if sum((duration, fixed, recurring)) != 1:
            raise ValueError("provide exactly one duration, fixed, or recurring session")
        if fixed and (self.starts_at is None or self.ends_at is None):
            raise ValueError("fixed sessions require starts_at and ends_at")
        if recurring and any(
            value is None
            for value in (
                self.recurrence_timezone,
                self.recurrence_local_start_time,
                self.recurrence_duration_seconds,
            )
        ):
            raise ValueError("recurring sessions require timezone, local start, and duration")
        return self

    def recurrence(self) -> RecurrenceRule | None:
        if self.recurrence_timezone is None:
            return None
        return RecurrenceRule(
            timezone=self.recurrence_timezone,
            local_start_time=str(self.recurrence_local_start_time),
            duration_seconds=int(self.recurrence_duration_seconds or 0),
            weekdays=tuple(self.recurrence_weekdays),
        )


class SessionResponse(BaseModel):
    id: str
    status: str
    admission_phase: str
    starts_at: datetime
    ends_at: datetime
    requested_at: datetime
    updated_at: datetime
    finished_at: datetime | None
    recurrence: dict[str, Any] | None
    recurrence_parent_id: str | None
    module_run_ids: dict[str, str]
    module_priorities: dict[str, int]
    resource_policy: dict[str, int]
    emergency_stop: bool
    result_summary: str | None

    @classmethod
    def from_snapshot(cls, snapshot: WorkSessionSnapshot) -> SessionResponse:
        return cls(
            id=snapshot.id,
            status=snapshot.status.value,
            admission_phase=snapshot.admission_phase.value,
            starts_at=snapshot.starts_at,
            ends_at=snapshot.ends_at,
            requested_at=snapshot.requested_at,
            updated_at=snapshot.updated_at,
            finished_at=snapshot.finished_at,
            recurrence=snapshot.recurrence.to_dict() if snapshot.recurrence else None,
            recurrence_parent_id=snapshot.recurrence_parent_id,
            module_run_ids=snapshot.module_run_ids,
            module_priorities=snapshot.module_priorities,
            resource_policy=snapshot.resource_policy,
            emergency_stop=snapshot.emergency_stop,
            result_summary=snapshot.result_summary,
        )


class WorkRequestCreateRequest(BaseModel):
    module_id: str = Field(min_length=1, max_length=100)
    run_id: str = Field(min_length=1, max_length=100)
    session_id: str | None = Field(default=None, max_length=100)
    task_id: str = Field(min_length=1, max_length=100)
    work_class: WorkClass
    payload: dict[str, Any]
    provenance: dict[str, Any] = Field(default_factory=dict)
    output_contract: dict[str, Any] = Field(default_factory=dict)
    requirements: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str = Field(min_length=1, max_length=255)
    module_priority: int = Field(default=10, ge=0, le=100)
    task_priority: int = Field(default=50, ge=0, le=100)
    max_retries: int = Field(default=2, ge=0, le=20)

    def to_domain(self) -> WorkRequestSpec:
        return WorkRequestSpec(**self.model_dump())


class WorkRequestResponse(BaseModel):
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

    @classmethod
    def from_snapshot(cls, snapshot: WorkRequestSnapshot) -> WorkRequestResponse:
        return cls(**asdict(snapshot))


class WorkAttemptResponse(BaseModel):
    id: str
    request_id: str
    number: int
    status: str
    worker_id: str
    claimed_at: datetime
    completed_at: datetime | None
    error_code: str | None
    detail: dict[str, Any]

    @classmethod
    def from_snapshot(cls, snapshot: WorkAttemptSnapshot) -> WorkAttemptResponse:
        return cls(**asdict(snapshot))


class WorkResultResponse(BaseModel):
    id: str
    request_id: str
    attempt_id: str
    module_id: str
    payload: dict[str, Any]
    created_at: datetime
    acknowledged_at: datetime | None
    delivery_count: int
    last_delivered_at: datetime | None

    @classmethod
    def from_snapshot(cls, snapshot: WorkResultSnapshot) -> WorkResultResponse:
        return cls(**asdict(snapshot))


class QueueStatusResponse(BaseModel):
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

    @classmethod
    def from_snapshot(cls, snapshot: QueueStatusSnapshot) -> QueueStatusResponse:
        return cls(**asdict(snapshot))


class WorkClaimRequest(BaseModel):
    worker_id: str = Field(min_length=1, max_length=100)
    work_classes: list[WorkClass] | None = None


class WorkCompleteRequest(BaseModel):
    payload: dict[str, Any]


class WorkFailRequest(BaseModel):
    error_code: str = Field(min_length=1, max_length=100)
    detail: dict[str, Any] = Field(default_factory=dict)
    retry_delay_seconds: float = Field(default=0, ge=0, le=86400)


class WorkPriorityRequest(BaseModel):
    task_priority: int = Field(ge=0, le=100)


class DocumentRegisterRequest(BaseModel):
    path: str = Field(min_length=1, max_length=4096)


class ProfileExtractRequest(BaseModel):
    document_id: str = Field(min_length=1, max_length=100)
    model: str | None = Field(default=None, min_length=1, max_length=200)


class HypothesisDecisionRequest(BaseModel):
    decision: HypothesisDecision


class ClaimDecisionRequest(BaseModel):
    decision: ClaimDecision


class ClaimOverrideRequest(BaseModel):
    label: str = Field(min_length=1, max_length=160)
    statement: str = Field(min_length=1, max_length=1000)
    category: ClaimCategory | None = None
