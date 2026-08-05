"""Authenticated loopback API used only by managed module workers."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from nerve_center.domain.module_runtime import ModuleRuntimeStatus
from nerve_center.domain.task import TaskResult, TaskStatus
from nerve_center.runtime.supervisor import (
    ModuleRuntimeAuthorizationError,
    ModuleRuntimeConflictError,
    ModuleSupervisor,
)


class HeartbeatRequest(BaseModel):
    status: ModuleRuntimeStatus
    activity: str = Field(min_length=1, max_length=500)
    deterministic_backlog: int = Field(default=0, ge=0)
    pending_llm_requests: int = Field(default=0, ge=0)
    queue_pressure: float = Field(default=0, ge=0, le=1)
    reason: str | None = Field(default=None, max_length=1000)


class CheckpointRequest(BaseModel):
    value: dict[str, Any]


class ResourceConsumptionRequest(BaseModel):
    resource: str
    count: int = Field(default=1, ge=1)


class OperationRequest(BaseModel):
    operation: str = Field(min_length=1, max_length=100)
    payload: dict[str, Any] = Field(default_factory=dict)


class CompletionRequest(BaseModel):
    status: TaskStatus
    summary: str = Field(min_length=1, max_length=2000)
    metrics: dict[str, int | float | str | bool] = Field(default_factory=dict)


def register_runtime_routes(application: FastAPI, supervisor: ModuleSupervisor) -> None:
    router = APIRouter(prefix="/runtime/v1/modules/{module_id}")

    def token(authorization: str = Header(default="")) -> str:
        scheme, _, value = authorization.partition(" ")
        if scheme.casefold() != "bearer" or not value:
            raise HTTPException(status_code=401, detail="module runtime token required")
        return value

    def translate(error: Exception) -> HTTPException:
        if isinstance(error, ModuleRuntimeAuthorizationError):
            return HTTPException(status_code=401, detail=str(error))
        if isinstance(error, (ModuleRuntimeConflictError, KeyError)):
            return HTTPException(status_code=409, detail=str(error))
        return HTTPException(status_code=422, detail=str(error))

    @router.post("/heartbeat")
    def heartbeat(
        module_id: str,
        request: HeartbeatRequest,
        authorization: str = Header(default=""),
    ) -> dict[str, Any]:
        try:
            report = supervisor.heartbeat(
                module_id,
                token(authorization),
                **request.model_dump(),
            )
            return report.to_dict()
        except Exception as error:
            raise translate(error) from error

    @router.get("/work")
    def next_work(module_id: str, authorization: str = Header(default="")) -> Any:
        try:
            return supervisor.next_assignment(module_id, token(authorization))
        except Exception as error:
            raise translate(error) from error

    @router.get("/control")
    def module_control(module_id: str, authorization: str = Header(default="")) -> Any:
        try:
            return supervisor.module_control(module_id, token(authorization))
        except Exception as error:
            raise translate(error) from error

    @router.get("/runs/{run_id}/control")
    def control(module_id: str, run_id: str, authorization: str = Header(default="")) -> Any:
        try:
            return supervisor.control(module_id, token(authorization), run_id)
        except Exception as error:
            raise translate(error) from error

    @router.post("/runs/{run_id}/checkpoint", status_code=204)
    def checkpoint(
        module_id: str,
        run_id: str,
        request: CheckpointRequest,
        authorization: str = Header(default=""),
    ) -> None:
        try:
            supervisor.checkpoint(module_id, token(authorization), run_id, request.value)
        except Exception as error:
            raise translate(error) from error

    @router.post("/runs/{run_id}/resources")
    def consume_resource(
        module_id: str,
        run_id: str,
        request: ResourceConsumptionRequest,
        authorization: str = Header(default=""),
    ) -> dict[str, int]:
        try:
            return supervisor.consume_resource(
                module_id,
                token(authorization),
                run_id,
                request.resource,
                request.count,
            )
        except Exception as error:
            raise translate(error) from error

    @router.post("/runs/{run_id}/operations")
    async def invoke(
        module_id: str,
        run_id: str,
        request: OperationRequest,
        authorization: str = Header(default=""),
    ) -> dict[str, Any]:
        try:
            return await supervisor.invoke(
                module_id,
                token(authorization),
                run_id,
                request.operation,
                request.payload,
            )
        except Exception as error:
            raise translate(error) from error

    @router.post("/runs/{run_id}/complete", status_code=204)
    def complete(
        module_id: str,
        run_id: str,
        request: CompletionRequest,
        authorization: str = Header(default=""),
    ) -> None:
        try:
            supervisor.complete(
                module_id,
                token(authorization),
                run_id,
                TaskResult(
                    status=request.status,
                    summary=request.summary,
                    metrics=request.metrics,
                ),
            )
        except Exception as error:
            raise translate(error) from error

    application.include_router(router)
