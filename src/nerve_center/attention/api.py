"""Manager API for durable Attention and Review work."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from nerve_center.attention.domain import AttentionKind, AttentionState
from nerve_center.attention.service import AttentionService


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AttentionCreateRequest(StrictRequest):
    kind: AttentionKind
    module_id: str = Field(min_length=1, max_length=100)
    source_type: str = Field(min_length=1, max_length=100)
    source_id: str = Field(min_length=1, max_length=100)
    idempotency_key: str = Field(min_length=1, max_length=255)
    title: str = Field(min_length=1, max_length=500)
    summary: str = Field(min_length=1, max_length=4000)
    context: dict[str, Any] = Field(default_factory=dict)
    allowed_dispositions: list[str] = Field(default_factory=list)
    validation: dict[str, Any] = Field(default_factory=dict)
    downstream_meaning: dict[str, Any] = Field(default_factory=dict)
    dependency_keys: list[str] = Field(default_factory=list)


class AttentionResolveRequest(StrictRequest):
    disposition: str = Field(min_length=1, max_length=100)
    detail: dict[str, Any] = Field(default_factory=dict)
    actor: str = Field(default="user", min_length=1, max_length=100)


class AttentionDismissRequest(StrictRequest):
    reason: str = Field(min_length=1, max_length=1000)
    actor: str = Field(default="user", min_length=1, max_length=100)


def register_attention_routes(
    application: FastAPI,
    service: AttentionService,
) -> None:
    router = APIRouter(prefix="/api/v1/attention", tags=["attention"])

    @router.post("", status_code=201)
    def create(request: AttentionCreateRequest) -> dict[str, Any]:
        item, created = service.submit(
            kind=request.kind,
            module_id=request.module_id,
            source_type=request.source_type,
            source_id=request.source_id,
            idempotency_key=request.idempotency_key,
            title=request.title,
            summary=request.summary,
            context=request.context,
            allowed_dispositions=tuple(request.allowed_dispositions),
            validation=request.validation,
            downstream_meaning=request.downstream_meaning,
            dependency_keys=tuple(request.dependency_keys),
        )
        return {"item": asdict(item), "created": created}

    @router.get("")
    def list_items(
        state: AttentionState | None = None,
        kind: AttentionKind | None = None,
        module_id: str | None = None,
        dependency_key: str | None = None,
        limit: int = Query(default=200, ge=1, le=1000),
    ) -> list[dict[str, Any]]:
        return [
            asdict(item)
            for item in service.list(
                state=state,
                kind=kind,
                module_id=module_id,
                dependency_key=dependency_key,
                limit=limit,
            )
        ]

    @router.get("/dependencies/{dependency_key}/blocked")
    def dependency_blocked(dependency_key: str) -> dict[str, object]:
        return {
            "dependency_key": dependency_key,
            "blocked": service.dependency_blocked(dependency_key),
        }

    @router.get("/{item_id}")
    def get_item(item_id: str) -> dict[str, Any]:
        try:
            return asdict(service.get(item_id))
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @router.get("/{item_id}/history")
    def history(item_id: str) -> list[dict[str, Any]]:
        try:
            return [asdict(event) for event in service.history(item_id)]
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @router.post("/{item_id}/resolve")
    def resolve(
        item_id: str,
        request: AttentionResolveRequest,
    ) -> dict[str, Any]:
        try:
            return asdict(
                service.resolve(
                    item_id,
                    disposition=request.disposition,
                    detail=request.detail,
                    actor=request.actor,
                )
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @router.post("/{item_id}/dismiss")
    def dismiss(
        item_id: str,
        request: AttentionDismissRequest,
    ) -> dict[str, Any]:
        try:
            return asdict(
                service.dismiss(
                    item_id,
                    reason=request.reason,
                    actor=request.actor,
                )
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    application.include_router(router)
