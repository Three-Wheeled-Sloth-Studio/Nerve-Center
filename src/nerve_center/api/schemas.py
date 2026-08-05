"""API request and response schemas."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Any, Self

from pydantic import BaseModel, Field, model_validator

from nerve_center.domain.budget import ResourceBudget
from nerve_center.domain.module import InstalledModule, ModuleLifecycleState
from nerve_center.domain.run import RunEventSnapshot, RunSnapshot, RunStatus
from nerve_center.domain.run_window import DurationRunWindow, FixedRunWindow
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

    @classmethod
    def from_installed(cls, installed: InstalledModule) -> ModuleResponse:
        return cls(
            manifest=installed.manifest.to_dict(),
            lifecycle_state=installed.lifecycle_state,
            saved_priority=installed.saved_priority,
        )


class DocumentRegisterRequest(BaseModel):
    path: str = Field(min_length=1, max_length=4096)


class ProfileExtractRequest(BaseModel):
    document_id: str = Field(min_length=1, max_length=100)
    model: str = Field(min_length=1, max_length=200)


class HypothesisDecisionRequest(BaseModel):
    decision: HypothesisDecision


class ClaimDecisionRequest(BaseModel):
    decision: ClaimDecision


class ClaimOverrideRequest(BaseModel):
    label: str = Field(min_length=1, max_length=160)
    statement: str = Field(min_length=1, max_length=1000)
    category: ClaimCategory | None = None
