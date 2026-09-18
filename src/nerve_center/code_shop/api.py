"""Manager API for Code Shop project, authority, and workflow contracts."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from nerve_center.code_shop.checkout import CheckoutValidationError
from nerve_center.code_shop.domain import (
    ActionPolicy,
    EngineeringCapability,
    ExecutionCapability,
    ExecutionRequest,
    ProjectAction,
    ProjectLifecycle,
)
from nerve_center.code_shop.service import AuthorityNotGrantedError, CodeShopService


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProjectUpdateRequest(StrictRequest):
    lifecycle: ProjectLifecycle | None = None
    priority: int | None = Field(default=None, ge=0, le=100)
    branch_policy: dict[str, Any] | None = None
    hosted_runner_eligible: bool | None = None


class CheckoutLinkRequest(StrictRequest):
    path: str = Field(min_length=1, max_length=4096)


class AuthorityPolicyRequest(StrictRequest):
    policy: ActionPolicy
    scope: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)


class TaskCreateRequest(StrictRequest):
    repository_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=500)
    capability: EngineeringCapability
    source_backlog: dict[str, Any] = Field(default_factory=dict)


class AttemptCreateRequest(StrictRequest):
    status: str = Field(pattern="^(started|succeeded|failed)$")
    approach: str = Field(min_length=1, max_length=4000)
    context_inputs: dict[str, Any] = Field(default_factory=dict)
    manager_provenance: dict[str, Any] = Field(default_factory=dict)
    touched_files: list[str] = Field(default_factory=list)
    command_summaries: list[str] = Field(default_factory=list)
    resources: dict[str, Any] = Field(default_factory=dict)
    outcome: dict[str, Any] = Field(default_factory=dict)
    max_failed_attempts: int = Field(default=3, ge=1, le=20)


class OutcomeCreateRequest(StrictRequest):
    attempt_id: str | None = Field(default=None, max_length=100)
    kind: str = Field(min_length=1, max_length=64)
    payload: dict[str, Any] = Field(default_factory=dict)


class EscalationCreateRequest(StrictRequest):
    reason: str = Field(min_length=1, max_length=1000)
    evidence: dict[str, Any] = Field(default_factory=dict)
    failed_invariant: str = Field(min_length=1, max_length=200)
    recommended_capability: str = Field(min_length=1, max_length=100)
    compact_handoff: str = Field(min_length=1, max_length=4000)
    dispositions: list[str] = Field(default_factory=list)


class ExecutionRequestBody(StrictRequest):
    module_id: str = Field(default="code_shop", min_length=1, max_length=100)
    task_id: str = Field(min_length=1, max_length=100)
    repository_id: str = Field(min_length=1, max_length=100)
    action: ProjectAction
    capability: ExecutionCapability
    arguments: dict[str, Any] = Field(default_factory=dict)
    expected_outputs: dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: int = Field(default=300, ge=1, le=86_400)
    resource_limits: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str = Field(min_length=1, max_length=255)
    branch: str | None = Field(default=None, max_length=255)
    resource_paths: list[str] = Field(default_factory=list)

    def to_domain(self) -> ExecutionRequest:
        return ExecutionRequest(
            module_id=self.module_id,
            task_id=self.task_id,
            repository_id=self.repository_id,
            action=self.action,
            capability=self.capability,
            arguments=dict(self.arguments),
            expected_outputs=dict(self.expected_outputs),
            timeout_seconds=self.timeout_seconds,
            resource_limits=dict(self.resource_limits),
            idempotency_key=self.idempotency_key,
            branch=self.branch,
            resource_paths=tuple(self.resource_paths),
        )


def register_code_shop_routes(application: FastAPI, service: CodeShopService) -> None:
    router = APIRouter(prefix="/api/v1/modules/code_shop", tags=["code-shop"])

    @router.get("/overview")
    def overview() -> dict[str, Any]:
        return service.overview()

    @router.get("/trust")
    def trust() -> dict[str, Any]:
        return asdict(service.trust_provenance("code_shop"))

    @router.get("/repositories/discovered")
    def discovered_repositories() -> list[dict[str, Any]]:
        return [asdict(item) for item in service.discover_repositories()]

    @router.post("/projects/{repository_id}/select", status_code=201)
    def select_project(repository_id: str) -> dict[str, Any]:
        try:
            return asdict(service.select_repository(repository_id))
        except Exception as error:
            raise _translate(error) from error

    @router.post("/projects/synchronize")
    def synchronize_projects() -> list[dict[str, Any]]:
        return [asdict(item) for item in service.synchronize_projects()]

    @router.get("/projects")
    def list_projects() -> list[dict[str, Any]]:
        return [asdict(item) for item in service.list_projects()]

    @router.patch("/projects/{repository_id}")
    def update_project(
        repository_id: str,
        request: ProjectUpdateRequest,
    ) -> dict[str, Any]:
        try:
            return asdict(
                service.configure_project(repository_id, **request.model_dump())
            )
        except Exception as error:
            raise _translate(error) from error

    @router.put("/projects/{repository_id}/checkout")
    def link_checkout(
        repository_id: str,
        request: CheckoutLinkRequest,
    ) -> dict[str, Any]:
        try:
            return asdict(service.link_checkout(repository_id, request.path))
        except Exception as error:
            raise _translate(error) from error

    @router.delete("/projects/{repository_id}/checkout", status_code=204)
    def unlink_checkout(repository_id: str) -> None:
        try:
            service.unlink_checkout(repository_id)
        except Exception as error:
            raise _translate(error) from error

    @router.get("/projects/{repository_id}/authority")
    def list_authority(repository_id: str) -> list[dict[str, Any]]:
        try:
            return [asdict(item) for item in service.policies(repository_id)]
        except Exception as error:
            raise _translate(error) from error

    @router.put("/projects/{repository_id}/authority/{action}")
    def set_authority(
        repository_id: str,
        action: ProjectAction,
        request: AuthorityPolicyRequest,
    ) -> dict[str, Any]:
        try:
            return asdict(
                service.set_policy(
                    repository_id,
                    action,
                    request.policy,
                    scope=request.scope,
                    provenance=request.provenance,
                )
            )
        except Exception as error:
            raise _translate(error) from error

    @router.post("/tasks", status_code=201)
    def create_task(request: TaskCreateRequest) -> dict[str, Any]:
        try:
            return asdict(service.create_task(**request.model_dump()))
        except Exception as error:
            raise _translate(error) from error

    @router.get("/tasks")
    def list_tasks(
        repository_id: str | None = None,
        limit: int = Query(default=200, ge=1, le=1000),
    ) -> list[dict[str, Any]]:
        return [asdict(item) for item in service.list_tasks(repository_id, limit)]

    @router.post("/tasks/{task_id}/attempts", status_code=201)
    def record_attempt(task_id: str, request: AttemptCreateRequest) -> dict[str, Any]:
        try:
            values = request.model_dump()
            values["touched_files"] = tuple(values["touched_files"])
            values["command_summaries"] = tuple(values["command_summaries"])
            attempt, escalation = service.record_attempt(task_id, **values)
            return {
                "attempt": asdict(attempt),
                "escalation": asdict(escalation) if escalation else None,
            }
        except Exception as error:
            raise _translate(error) from error

    @router.post("/tasks/{task_id}/outcomes", status_code=201)
    def record_outcome(task_id: str, request: OutcomeCreateRequest) -> dict[str, Any]:
        try:
            return asdict(service.record_outcome(task_id, **request.model_dump()))
        except Exception as error:
            raise _translate(error) from error

    @router.post("/tasks/{task_id}/escalations", status_code=201)
    def raise_escalation(
        task_id: str,
        request: EscalationCreateRequest,
    ) -> dict[str, Any]:
        try:
            values = request.model_dump()
            if values["dispositions"]:
                values["dispositions"] = tuple(values["dispositions"])
            else:
                values.pop("dispositions")
            return asdict(service.raise_escalation(task_id, **values))
        except Exception as error:
            raise _translate(error) from error

    @router.get("/escalations")
    def list_escalations(
        task_id: str | None = None,
        limit: int = Query(default=200, ge=1, le=1000),
    ) -> list[dict[str, Any]]:
        return [asdict(item) for item in service.list_escalations(task_id, limit)]

    @router.post("/execution/evaluate")
    def evaluate_execution(request: ExecutionRequestBody) -> dict[str, Any]:
        try:
            return asdict(service.evaluate(request.to_domain()))
        except Exception as error:
            raise _translate(error) from error

    @router.post("/execution/execute")
    def execute(request: ExecutionRequestBody) -> dict[str, Any]:
        try:
            decision, result = service.execute(request.to_domain())
            return {"decision": asdict(decision), "result": asdict(result)}
        except Exception as error:
            raise _translate(error) from error

    application.include_router(router)


def _translate(error: Exception) -> HTTPException:
    if isinstance(error, KeyError):
        return HTTPException(status_code=404, detail=str(error))
    if isinstance(error, AuthorityNotGrantedError):
        return HTTPException(status_code=409, detail=str(error))
    if isinstance(error, CheckoutValidationError):
        return HTTPException(status_code=422, detail=str(error))
    if isinstance(error, ValueError):
        return HTTPException(status_code=422, detail=str(error))
    return HTTPException(status_code=500, detail=str(error))
