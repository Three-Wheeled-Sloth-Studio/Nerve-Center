"""Manager-owned resource-profile application service."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from nerve_center.persistence.resource_profiles import ResourceProfileRepository
from nerve_center.resource_profiles.domain import (
    MANAGER_DEFAULT_PROFILE_ID,
    RESOURCE_LIMIT_FIELDS,
    EffectiveResourceProfile,
    ResourceProfile,
    enforcement_map,
    manager_default_limits,
    normalize_limits,
)


class ResourceProfileService:
    def __init__(self, repository: ResourceProfileRepository) -> None:
        self.repository = repository

    def initialize(self) -> None:
        self.repository.initialize()

    def list(self) -> list[dict[str, Any]]:
        selected_id = self.repository.selected_id()
        return [self._profile_dict(item, selected_id) for item in self.repository.list()]

    def get(self, profile_id: str) -> dict[str, Any]:
        selected_id = self.repository.selected_id()
        return self._profile_dict(self.repository.get(profile_id), selected_id)

    def create(
        self,
        display_name: str,
        limits: dict[str, int | float],
    ) -> dict[str, Any]:
        selected_id = self.repository.selected_id()
        return self._profile_dict(
            self.repository.create(display_name, normalize_limits(limits)),
            selected_id,
        )

    def update(
        self,
        profile_id: str,
        *,
        display_name: str | None = None,
        limits: dict[str, int | float] | None = None,
    ) -> dict[str, Any]:
        selected_id = self.repository.selected_id()
        profile = self.repository.update(
            profile_id,
            display_name=display_name,
            limits=normalize_limits(limits) if limits is not None else None,
        )
        return self._profile_dict(profile, selected_id)

    def select(self, profile_id: str) -> dict[str, Any]:
        profile = self.repository.select(profile_id)
        return self._profile_dict(profile, profile.id)

    def selected(self) -> dict[str, Any]:
        return self.get(self.repository.selected_id())

    def resolve(
        self,
        *,
        profile_id: str | None = None,
        overrides: dict[str, int | float] | None = None,
    ) -> EffectiveResourceProfile:
        default = self.repository.get(MANAGER_DEFAULT_PROFILE_ID)
        chosen_id = profile_id or self.repository.selected_id()
        chosen = self.repository.get(chosen_id)
        normalized_overrides = normalize_limits(overrides)

        values: dict[str, int | float | None] = dict.fromkeys(
            RESOURCE_LIMIT_FIELDS, None
        )
        sources: dict[str, str] = dict.fromkeys(RESOURCE_LIMIT_FIELDS, "unset")

        for field, value in manager_default_limits().items():
            values[field] = value
            sources[field] = "manager_builtin_fallback"
        for field, value in default.limits.items():
            values[field] = value
            sources[field] = f"profile:{default.id}"
        if chosen.id != default.id:
            for field, value in chosen.limits.items():
                values[field] = value
                sources[field] = f"profile:{chosen.id}"
        for field, value in normalized_overrides.items():
            values[field] = value
            sources[field] = "session_override"

        return EffectiveResourceProfile(
            profile_id=chosen.id,
            limits=values,
            enforcement=enforcement_map(),
            source_by_field=sources,
            authorizes_cloud_spend=False,
        )

    @staticmethod
    def _profile_dict(
        profile: ResourceProfile,
        selected_id: str,
    ) -> dict[str, Any]:
        values = asdict(profile)
        values["selected"] = profile.id == selected_id
        return values
