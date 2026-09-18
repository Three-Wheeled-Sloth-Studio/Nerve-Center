"""API schemas shared by resource-profile and session surfaces."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ResourceLimitsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_requests: int | None = Field(default=None, ge=1)
    max_llm_calls: int | None = Field(default=None, ge=1)
    max_parallel_work: int | None = Field(default=None, ge=1, le=100)
    max_memory_mb: int | None = Field(default=None, ge=1)
    max_vram_mb: int | None = Field(default=None, ge=1)
    max_queue_depth: int | None = Field(default=None, ge=1)
    max_exploration_units: int | None = Field(default=None, ge=1)
    max_cloud_spend_usd: float | None = Field(default=None, gt=0)

    def to_mapping(self) -> dict[str, int | float]:
        return {
            key: value
            for key, value in self.model_dump().items()
            if value is not None
        }


class ResourceProfileCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(min_length=1, max_length=120)
    limits: ResourceLimitsRequest = Field(default_factory=ResourceLimitsRequest)


class ResourceProfileUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    limits: ResourceLimitsRequest | None = None

    @model_validator(mode="after")
    def require_change(self) -> ResourceProfileUpdateRequest:
        if self.display_name is None and self.limits is None:
            raise ValueError("provide display_name or limits")
        return self


class ResourceProfileResolveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: str | None = Field(default=None, min_length=1, max_length=100)
    overrides: ResourceLimitsRequest = Field(default_factory=ResourceLimitsRequest)
