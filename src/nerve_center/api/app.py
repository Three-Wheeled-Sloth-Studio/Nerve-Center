"""Local API bootstrap and run-control surface."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from typing import Annotated

import uvicorn
from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware

from nerve_center import __version__
from nerve_center.api.schemas import (
    ModuleLifecycleRequest,
    ModuleResponse,
    QueueStatusResponse,
    RunCreateRequest,
    RunEventResponse,
    RunResponse,
    SessionCreateRequest,
    SessionResponse,
    WorkAttemptResponse,
    WorkClaimRequest,
    WorkCompleteRequest,
    WorkFailRequest,
    WorkPriorityRequest,
    WorkRequestCreateRequest,
    WorkRequestResponse,
    WorkResultResponse,
)
from nerve_center.config import Settings
from nerve_center.domain.run import (
    InvalidRunTransitionError,
    RunNotFoundError,
    RunNotReadyError,
)
from nerve_center.domain.work_queue import (
    QueueLimitExceededError,
    WorkAttemptNotFoundError,
    WorkQueueConflictError,
    WorkRequestNotFoundError,
    WorkRequestStatus,
)
from nerve_center.model_lab.api import register_model_lab_routes
from nerve_center.model_lab.service import ModelLabService
from nerve_center.persistence.database import Database
from nerve_center.persistence.model_lab import ModelLabRepository
from nerve_center.persistence.modules import ModuleNotFoundError, ModuleRepository
from nerve_center.persistence.providers import ModelEvidenceRepository, ProviderCallRepository
from nerve_center.persistence.runs import RunRepository
from nerve_center.persistence.sessions import SessionNotFoundError, SessionRepository
from nerve_center.persistence.work_queue import WorkQueueRepository
from nerve_center.plugins.job_scout.bootstrap import install_job_scout
from nerve_center.plugins.synthetic import SyntheticTaskPlugin
from nerve_center.providers.base import JsonProvider, StructuredProvider
from nerve_center.providers.errors import ProviderError
from nerve_center.providers.manager import ProviderManager
from nerve_center.providers.ollama import OllamaProvider
from nerve_center.runtime.api import register_runtime_routes
from nerve_center.runtime.plugin import ModuleProcessTaskPlugin
from nerve_center.runtime.supervisor import ModuleSupervisor
from nerve_center.scheduler.provider_worker import ProviderWorkExecutor
from nerve_center.scheduler.registry import TaskRegistry
from nerve_center.scheduler.runner import RunnerService
from nerve_center.scheduler.service import SchedulerService
from nerve_center.scheduler.sessions import WorkSessionConflictError, WorkSessionService
from nerve_center.scheduler.work_queue import WorkQueueService

LOCAL_DESKTOP_ORIGINS = [
    "http://127.0.0.1:1420",
    "http://localhost:1420",
    "http://tauri.localhost",
    "https://tauri.localhost",
    "tauri://localhost",
]


def create_app(
    settings: Settings | None = None,
    provider: StructuredProvider | None = None,
) -> FastAPI:
    runtime_settings = settings or Settings()
    database = Database(runtime_settings)
    repository = RunRepository(database)
    module_repository = ModuleRepository(database)
    session_repository = SessionRepository(database)
    model_evidence = ModelEvidenceRepository(database)
    model_lab_repository = ModelLabRepository(database)
    work_queue = WorkQueueService(
        WorkQueueRepository(database), model_evidence=model_evidence
    )
    provider_manager: ProviderManager | None = None
    runtime_provider = provider
    if runtime_provider is None:
        ollama = OllamaProvider(
            base_url=runtime_settings.ollama_base_url,
            timeout_seconds=runtime_settings.ollama_timeout_seconds,
            telemetry=ProviderCallRepository(database),
        )
        provider_manager = ProviderManager(
            (ollama,),
            evidence=model_evidence,
            preferred_model=runtime_settings.ollama_default_model,
            schema_fallback_model=runtime_settings.ollama_schema_fallback_model,
            allow_model_fallback=runtime_settings.ollama_allow_model_fallback,
        )
        runtime_provider = provider_manager
    elif isinstance(runtime_provider, JsonProvider):
        provider_manager = ProviderManager((runtime_provider,), evidence=model_evidence)
    model_lab = ModelLabService(
        model_lab_repository,
        model_evidence,
        provider_manager,
        work_queue,
    )
    registry = TaskRegistry()
    registry.register(SyntheticTaskPlugin())

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        database.initialize()
        module_repository.synchronize(registry.list_modules())
        runner.recover_interrupted()
        work_queue.recover_interrupted()
        work_sessions.recover()
        await scheduler.start()
        yield
        await scheduler.stop()
        await runner.shutdown()
        await module_supervisor.shutdown()

    application = FastAPI(
        title="Nerve Center",
        version=__version__,
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=LOCAL_DESKTOP_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.state.repository = repository
    application.state.module_repository = module_repository
    job_scout = install_job_scout(
        application,
        database,
        runtime_settings,
        runtime_provider,
    )
    module_supervisor = ModuleSupervisor(runtime_settings)
    module_supervisor.register(job_scout.manifest, job_scout.operation_bridge)
    registry.register_module(
        job_scout.manifest,
        tuple(
            ModuleProcessTaskPlugin(
                module_supervisor,
                job_scout.manifest,
                declaration.task_id,
                declaration.display_name,
            )
            for declaration in job_scout.manifest.task_types
        ),
    )
    runner = RunnerService(
        repository,
        registry,
        module_lifecycle=lambda module_id: module_repository.get(module_id).lifecycle_state,
    )
    work_sessions = WorkSessionService(
        session_repository,
        module_repository,
        repository,
        registry,
        runner,
        module_supervisor,
    )
    module_supervisor.set_session_control_resolver(work_sessions.control)
    module_supervisor.set_work_queue(work_queue)
    provider_executor = (
        ProviderWorkExecutor(work_queue, provider_manager) if provider_manager else None
    )
    scheduler = SchedulerService(
        repository,
        runner,
        poll_seconds=runtime_settings.scheduler_poll_seconds,
        session_tick=work_sessions.tick,
        queue_tick=provider_executor.tick if provider_executor else None,
    )
    application.state.runner = runner
    application.state.scheduler = scheduler
    application.state.module_supervisor = module_supervisor
    application.state.work_sessions = work_sessions
    application.state.work_queue = work_queue
    application.state.provider_manager = provider_manager
    application.state.model_lab = model_lab
    register_runtime_routes(application, module_supervisor)
    register_model_lab_routes(application, model_lab)

    def queue_error(error: Exception) -> HTTPException:
        if isinstance(error, (WorkRequestNotFoundError, WorkAttemptNotFoundError)):
            return HTTPException(status_code=404, detail=str(error))
        if isinstance(error, QueueLimitExceededError):
            return HTTPException(status_code=429, detail=str(error))
        if isinstance(error, WorkQueueConflictError):
            return HTTPException(status_code=409, detail=str(error))
        return HTTPException(status_code=422, detail=str(error))

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @application.get("/api/v1/providers/models")
    async def list_provider_models() -> list[object]:
        if provider_manager is not None:
            with suppress(ProviderError):
                await provider_manager.list_models()
        return list(model_evidence.list_models())

    @application.get("/api/v1/providers/evidence/{task_id}")
    def list_provider_evidence(task_id: str) -> list[object]:
        return list(model_evidence.task_evidence(task_id))

    @application.post("/api/v1/sessions", status_code=status.HTTP_201_CREATED)
    async def create_session(request: SessionCreateRequest) -> SessionResponse:
        try:
            recurrence = request.recurrence()
            resource_policy = request.resource_policy.model_dump()
            if request.duration_seconds is not None:
                snapshot = work_sessions.create_duration(
                    request.duration_seconds, resource_policy=resource_policy
                )
            elif recurrence is not None:
                snapshot = work_sessions.create_recurring(
                    recurrence, resource_policy=resource_policy
                )
            else:
                if request.starts_at is None or request.ends_at is None:
                    raise ValueError("fixed session window is incomplete")
                snapshot = work_sessions.create_fixed(
                    request.starts_at,
                    request.ends_at,
                    resource_policy=resource_policy,
                )
            if snapshot.status.value == "requested":
                snapshot = await work_sessions.start(snapshot.id)
            return SessionResponse.from_snapshot(snapshot)
        except WorkSessionConflictError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @application.get("/api/v1/sessions")
    def list_sessions(
        limit: Annotated[int, Query(ge=1, le=500)] = 100,
    ) -> list[SessionResponse]:
        return [
            SessionResponse.from_snapshot(item)
            for item in session_repository.list_recent(limit)
        ]

    @application.get("/api/v1/sessions/{session_id}")
    def get_session(session_id: str) -> SessionResponse:
        try:
            return SessionResponse.from_snapshot(session_repository.get(session_id))
        except SessionNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @application.post("/api/v1/sessions/{session_id}/start")
    async def start_session(session_id: str) -> SessionResponse:
        try:
            return SessionResponse.from_snapshot(await work_sessions.start(session_id))
        except SessionNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except WorkSessionConflictError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @application.post("/api/v1/sessions/{session_id}/emergency-stop")
    async def emergency_stop_session(session_id: str) -> SessionResponse:
        try:
            return SessionResponse.from_snapshot(
                await work_sessions.emergency_stop(session_id)
            )
        except SessionNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @application.post(
        "/api/v1/work-requests",
        status_code=status.HTTP_201_CREATED,
    )
    def submit_work_request(request: WorkRequestCreateRequest) -> WorkRequestResponse:
        try:
            return WorkRequestResponse.from_snapshot(work_queue.submit(request.to_domain()))
        except Exception as error:
            raise queue_error(error) from error

    @application.get("/api/v1/work-requests")
    def list_work_requests(
        module_id: str | None = None,
        request_status: WorkRequestStatus | None = None,
        limit: Annotated[int, Query(ge=1, le=1000)] = 200,
    ) -> list[WorkRequestResponse]:
        return [
            WorkRequestResponse.from_snapshot(item)
            for item in work_queue.list_requests(
                module_id=module_id, status=request_status, limit=limit
            )
        ]

    @application.get("/api/v1/work-requests/status")
    def work_queue_status(module_id: str | None = None) -> QueueStatusResponse:
        return QueueStatusResponse.from_snapshot(work_queue.status(module_id))

    @application.get("/api/v1/work-requests/{request_id}")
    def get_work_request(request_id: str) -> WorkRequestResponse:
        try:
            return WorkRequestResponse.from_snapshot(work_queue.get(request_id))
        except Exception as error:
            raise queue_error(error) from error

    @application.get("/api/v1/work-requests/{request_id}/attempts")
    def get_work_attempts(request_id: str) -> list[WorkAttemptResponse]:
        try:
            return [
                WorkAttemptResponse.from_snapshot(item)
                for item in work_queue.attempts(request_id)
            ]
        except Exception as error:
            raise queue_error(error) from error

    @application.post("/api/v1/work-requests/claim")
    def claim_work(request: WorkClaimRequest) -> WorkAttemptResponse | None:
        attempt = work_queue.claim_next(
            request.worker_id,
            tuple(request.work_classes) if request.work_classes else None,
        )
        return WorkAttemptResponse.from_snapshot(attempt) if attempt else None

    @application.post("/api/v1/work-attempts/{attempt_id}/complete")
    def complete_work_attempt(
        attempt_id: str, request: WorkCompleteRequest
    ) -> WorkResultResponse:
        try:
            return WorkResultResponse.from_snapshot(
                work_queue.complete(attempt_id, request.payload)
            )
        except Exception as error:
            raise queue_error(error) from error

    @application.post("/api/v1/work-attempts/{attempt_id}/fail")
    def fail_work_attempt(
        attempt_id: str, request: WorkFailRequest
    ) -> WorkRequestResponse:
        try:
            return WorkRequestResponse.from_snapshot(
                work_queue.fail(
                    attempt_id,
                    request.error_code,
                    detail=request.detail,
                    retry_delay_seconds=request.retry_delay_seconds,
                )
            )
        except Exception as error:
            raise queue_error(error) from error

    @application.post("/api/v1/work-requests/{request_id}/cancel")
    def cancel_work_request(request_id: str) -> WorkRequestResponse:
        try:
            return WorkRequestResponse.from_snapshot(work_queue.cancel(request_id))
        except Exception as error:
            raise queue_error(error) from error

    @application.post("/api/v1/work-requests/{request_id}/retry")
    def retry_work_request(request_id: str) -> WorkRequestResponse:
        try:
            return WorkRequestResponse.from_snapshot(work_queue.retry(request_id))
        except Exception as error:
            raise queue_error(error) from error

    @application.patch("/api/v1/work-requests/{request_id}/priority")
    def reprioritize_work_request(
        request_id: str, request: WorkPriorityRequest
    ) -> WorkRequestResponse:
        try:
            return WorkRequestResponse.from_snapshot(
                work_queue.reprioritize(request_id, request.task_priority)
            )
        except Exception as error:
            raise queue_error(error) from error

    @application.get("/api/v1/modules")
    def list_modules() -> list[ModuleResponse]:
        return [
            ModuleResponse.from_installed(
                item,
                module_supervisor.report(item.manifest.module_id),
            )
            for item in module_repository.list()
        ]

    @application.get("/api/v1/modules/{module_id}")
    def get_module(module_id: str) -> ModuleResponse:
        try:
            return ModuleResponse.from_installed(
                module_repository.get(module_id), module_supervisor.report(module_id)
            )
        except ModuleNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @application.patch("/api/v1/modules/{module_id}")
    async def update_module(
        module_id: str,
        request: ModuleLifecycleRequest,
    ) -> ModuleResponse:
        try:
            installed = module_repository.set_lifecycle(module_id, request.lifecycle_state)
            if request.lifecycle_state.value == "paused":
                await module_supervisor.stop(module_id)
            return ModuleResponse.from_installed(installed, module_supervisor.report(module_id))
        except ModuleNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @application.post("/api/v1/runs", status_code=status.HTTP_201_CREATED)
    def create_run(request: RunCreateRequest) -> RunResponse:
        try:
            registry.get(request.task_id)
            module = registry.module_for_task(request.task_id)
            if module is not None:
                installed = module_repository.get(module.module_id)
                if installed.lifecycle_state.value != "enabled":
                    raise HTTPException(
                        status_code=409,
                        detail=f"module {module.module_id} is {installed.lifecycle_state.value}",
                    )
            snapshot = repository.create(
                task_id=request.task_id,
                window=request.to_window(),
                configuration=request.configuration,
                budget=request.budget.to_domain(),
            )
            return RunResponse.from_snapshot(snapshot)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @application.get("/api/v1/runs")
    def list_runs(
        limit: Annotated[int, Query(ge=1, le=500)] = 100,
    ) -> list[RunResponse]:
        return [RunResponse.from_snapshot(item) for item in repository.list_recent(limit)]

    @application.get("/api/v1/runs/{run_id}")
    def get_run(run_id: str) -> RunResponse:
        try:
            return RunResponse.from_snapshot(repository.get(run_id))
        except RunNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @application.get("/api/v1/runs/{run_id}/events")
    def get_run_events(
        run_id: str,
        limit: Annotated[int, Query(ge=1, le=2000)] = 500,
    ) -> list[RunEventResponse]:
        try:
            return [
                RunEventResponse.from_snapshot(item)
                for item in repository.list_events(run_id, limit)
            ]
        except RunNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @application.post("/api/v1/runs/{run_id}/start")
    async def start_run(run_id: str) -> RunResponse:
        try:
            return RunResponse.from_snapshot(await runner.start(run_id))
        except RunNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except (InvalidRunTransitionError, RunNotReadyError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @application.post("/api/v1/runs/{run_id}/cancel")
    def cancel_run(run_id: str) -> RunResponse:
        try:
            return RunResponse.from_snapshot(runner.cancel(run_id))
        except RunNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    return application


app = create_app()


def run() -> None:
    settings = Settings()
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        reload=False,
    )
