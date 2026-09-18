"""Manager-owned resource-profile contracts and deterministic resolution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Mapping

from nerve_center.domain.budget import ResourceBudget

MANAGER_DEFAULT_PROFILE_ID = "manager-default"

RESOURCE_LIMIT_FIELDS = (
    "max_requests",
    "max_llm_calls",
    "max_parallel_work",
    "max_memory_mb",
    "max_vram_mb",
    "max_queue_depth",
    "max_exploration_units",
    "max_cloud_spend_usd",
)

INTEGER_LIMIT_FIELDS = frozenset(
    {
        "max_requests",
        "max_llm_calls",
        "max_parallel_work",
        "max_memory_mb",
        "max_vram_mb",
        "max_queue_depth",
        "max_exploration_units",
    }
)

ENFORCED_LIMIT_FIELDS = frozenset(
    {
        "max_requests",
        "max_llm_calls",
        "max_parallel_work",
    }
)


class ResourceEnforcement(StrEnum):
    ENFORCED = "enforced"
    UNENFORCED = "unenforced"
    UNENFORCED_NO_AUTHORITY = "unenforced_no_authority"


@dataclass(frozen=True, slots=True)
class ResourceProfile:
    id: str
    display_name: str
    limits: dict[str, int | float]
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class EffectiveResourceProfile:
    profile_id: str
    limits: dict[str, int | float | None]
    enforcement: dict[str, str]
    source_by_field: dict[str, str]
    authorizes_cloud_spend: bool = False

    def enforced_budget(self) -> ResourceBudget:
        return ResourceBudget(
            max_requests=int(self.limits["max_requests"]),
            max_llm_calls=int(self.limits["max_llm_calls"]),
            max_parallel_work=int(self.limits["max_parallel_work"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "limits": dict(self.limits),
            "enforcement": dict(self.enforcement),
            "source_by_field": dict(self.source_by_field),
            "authorizes_cloud_spend": self.authorizes_cloud_spend,
        }


def manager_default_limits() -> dict[str, int | float]:
    budget = ResourceBudget()
    return {
        "max_requests": budget.max_requests,
        "max_llm_calls": budget.max_llm_calls,
        "max_parallel_work": budget.max_parallel_work,
    }


def normalize_limits(
    values: Mapping[str, object] | None,
) -> dict[str, int | float]:
    if values is None:
        return {}
    unknown = sorted(set(values) - set(RESOURCE_LIMIT_FIELDS))
    if unknown:
        raise ValueError(f"unknown resource limit fields: {', '.join(unknown)}")

    normalized: dict[str, int | float] = {}
    for field in RESOURCE_LIMIT_FIELDS:
        raw = values.get(field)
        if raw is None:
            continue
        if field in INTEGER_LIMIT_FIELDS:
            if isinstance(raw, bool) or not isinstance(raw, int):
                raise ValueError(f"{field} must be an integer")
            if raw < 1:
                raise ValueError(f"{field} must be at least 1")
            normalized[field] = raw
            continue
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            raise ValueError(f"{field} must be numeric")
        numeric = float(raw)
        if numeric <= 0:
            raise ValueError(f"{field} must be greater than 0")
        normalized[field] = numeric
    return normalized


def enforcement_map() -> dict[str, str]:
    values: dict[str, str] = {}
    for field in RESOURCE_LIMIT_FIELDS:
        if field in ENFORCED_LIMIT_FIELDS:
            values[field] = ResourceEnforcement.ENFORCED.value
        elif field == "max_cloud_spend_usd":
            values[field] = ResourceEnforcement.UNENFORCED_NO_AUTHORITY.value
        else:
            values[field] = ResourceEnforcement.UNENFORCED.value
    return values
