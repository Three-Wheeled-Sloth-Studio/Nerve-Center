"""Manager API for module permission review."""

from __future__ import annotations

from dataclasses import asdict
from typing import Annotated, Any

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from nerve_center.module_permissions.domain import PermissionReviewState
from nerve_center.module_permissions.service import ModulePermissionReviewService


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PermissionDecisionRequest(StrictRequest):
    actor: str = Field(default="user", min_length=1, max_length=100)
    provenance: dict[str, Any] = Field(default_factory=dict)


def register_module_permission_routes(
    application: FastAPI,
    service: ModulePermissionReviewService,
) -> None:
    @application.get("/api/v1/module-permissions")
    def list_reviews(
        module_id: str | None = None,
        state: PermissionReviewState | None = None,
        limit: Annotated[int, Query(ge=1, le=1000)] = 200,
    ) -> list[dict[str, Any]]:
        return [
            asdict(item)
            for item in service.list(
                module_id=module_id,
                state=state,
                limit=limit,
            )
        ]

    @application.get("/api/v1/module-permissions/{review_id}")
    def get_review(review_id: str) -> dict[str, Any]:
        try:
            return asdict(service.get(review_id))
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @application.post(
        "/api/v1/module-permissions/{review_id}/permissions/{permission_key}/approve"
    )
    def approve(
        review_id: str,
        permission_key: str,
        request: PermissionDecisionRequest,
    ) -> dict[str, Any]:
        try:
            return asdict(
                service.approve(
                    review_id,
                    permission_key,
                    actor=request.actor,
                    provenance=request.provenance,
                )
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @application.post(
        "/api/v1/module-permissions/{review_id}/permissions/{permission_key}/deny"
    )
    def deny(
        review_id: str,
        permission_key: str,
        request: PermissionDecisionRequest,
    ) -> dict[str, Any]:
        try:
            return asdict(
                service.deny(
                    review_id,
                    permission_key,
                    actor=request.actor,
                    provenance=request.provenance,
                )
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
