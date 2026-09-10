"""Local manager API for Model Lab inspection and bounded exploration."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException
from pydantic import BaseModel, Field

from nerve_center.model_lab.service import (
    ModelLabBusyError,
    ModelLabDisabledError,
    ModelLabService,
)


class ModelLabSettingsRequest(BaseModel):
    enabled: bool = True
    capture_enabled: bool = True
    excluded_modules: list[str] = Field(default_factory=list)


class ModelLabSessionRequest(BaseModel):
    duration_seconds: int = Field(ge=1, le=86_400)
    max_attempts: int = Field(default=10, ge=1, le=10_000)


class ModelLabReplayRequest(BaseModel):
    provider: str = Field(min_length=1, max_length=50)
    model: str = Field(min_length=1, max_length=200)


def register_model_lab_routes(application: FastAPI, service: ModelLabService) -> None:
    router = APIRouter(prefix="/api/v1/model-lab", tags=["model-lab"])

    @router.get("")
    async def overview() -> dict[str, Any]:
        return await service.overview()

    @router.put("/settings")
    def update_settings(request: ModelLabSettingsRequest) -> dict[str, Any]:
        return asdict(service.update_settings(**request.model_dump()))

    @router.post("/sessions", status_code=201)
    def start_session(request: ModelLabSessionRequest) -> dict[str, Any]:
        try:
            return asdict(service.start_exploration(**request.model_dump()))
        except Exception as error:
            raise _translate(error) from error

    @router.post("/corpus/{corpus_id}/replay")
    async def replay(
        corpus_id: str, request: ModelLabReplayRequest
    ) -> dict[str, Any]:
        try:
            return asdict(
                await service.replay(
                    corpus_id,
                    provider=request.provider,
                    model=request.model,
                )
            )
        except Exception as error:
            raise _translate(error) from error

    application.include_router(router)


def _translate(error: Exception) -> HTTPException:
    if isinstance(error, KeyError):
        return HTTPException(status_code=404, detail=str(error))
    if isinstance(error, (ModelLabBusyError, ModelLabDisabledError)):
        return HTTPException(status_code=409, detail=str(error))
    if isinstance(error, ValueError):
        return HTTPException(status_code=422, detail=str(error))
    return HTTPException(status_code=500, detail=str(error))
