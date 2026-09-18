"""Manager API for reusable resource profiles."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, status

from nerve_center.persistence.resource_profiles import ResourceProfileNotFoundError
from nerve_center.resource_profiles.schemas import (
    ResourceProfileCreateRequest,
    ResourceProfileResolveRequest,
    ResourceProfileUpdateRequest,
)
from nerve_center.resource_profiles.service import ResourceProfileService


def register_resource_profile_routes(
    application: FastAPI,
    service: ResourceProfileService,
) -> None:
    @application.get("/api/v1/resource-profiles")
    def list_profiles() -> list[dict[str, Any]]:
        return service.list()

    @application.post(
        "/api/v1/resource-profiles",
        status_code=status.HTTP_201_CREATED,
    )
    def create_profile(request: ResourceProfileCreateRequest) -> dict[str, Any]:
        try:
            return service.create(request.display_name, request.limits.to_mapping())
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @application.get("/api/v1/resource-profiles/selected")
    def selected_profile() -> dict[str, Any]:
        return service.selected()

    @application.post("/api/v1/resource-profiles/resolve")
    def resolve_profile(
        request: ResourceProfileResolveRequest,
    ) -> dict[str, Any]:
        try:
            return service.resolve(
                profile_id=request.profile_id,
                overrides=request.overrides.to_mapping(),
            ).to_dict()
        except ResourceProfileNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @application.get("/api/v1/resource-profiles/{profile_id}")
    def get_profile(profile_id: str) -> dict[str, Any]:
        try:
            return service.get(profile_id)
        except ResourceProfileNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @application.patch("/api/v1/resource-profiles/{profile_id}")
    def update_profile(
        profile_id: str,
        request: ResourceProfileUpdateRequest,
    ) -> dict[str, Any]:
        try:
            return service.update(
                profile_id,
                display_name=request.display_name,
                limits=request.limits.to_mapping() if request.limits is not None else None,
            )
        except ResourceProfileNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @application.post("/api/v1/resource-profiles/{profile_id}/select")
    def select_profile(profile_id: str) -> dict[str, Any]:
        try:
            return service.select(profile_id)
        except ResourceProfileNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
