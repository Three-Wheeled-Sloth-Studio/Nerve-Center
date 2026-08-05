"""Local API bootstrap and run-control surface."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

import uvicorn
from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware

from nerve_center import __version__
from nerve_center.api.schemas import (
    ModuleLifecycleRequest,
    ModuleResponse,
    RunCreateRequest,
    RunEventResponse,
    RunResponse,
    SessionCreateRequest,
    SessionResponse,
)
from nerve_center.config import Settings
from nerve_center.domain.run import (
    InvalidRunTransitionError,
    RunNotFoundError,
    RunNotReadyError,
)
from nerve_center.persistence.database import Database
from nerve_center.persistence.modules import ModuleNotFoundError, ModuleRepository
from nerve_center.persistence.runs import RunRepository
from nerve_center.persistence.sessions import SessionNotFoundError, SessionRepository
from nerve_center.plugins.job_scout.bootstrap import install_job_scout
from nerve_center.plugins.synthetic import SyntheticTaskPlugin
from nerve_center.providers.base import StructuredProvider
from nerve_center.runtime.api import register_runtime_routes
from nerve_center.runtime.plugin import ModuleProcessTaskPlugin
from nerve_center.runtime.supervisor import ModuleSupervisor
from nerve_center.scheduler.registry import TaskRegistry
from nerve_center.scheduler.runner import RunnerService
from nerve_center.scheduler.service import SchedulerService
from nerve_center.scheduler.sessions import WorkSessionService

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
    registry = TaskRegistry()
    registry.register(SyntheticTaskPlugin())

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        database.initialize()
        module_repository.synchronize(registry.list_modules())
        runner.recover_interrupted()
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
        provider,
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
    scheduler = SchedulerService(
        repository,
        runner,
        poll_seconds=runtime_settings.scheduler_poll_seconds,
        session_tick=work_sessions.tick,
    )
    application.state.runner = runner
    application.state.scheduler = scheduler
    application.state.module_supervisor = module_supervisor
    application.state.work_sessions = work_sessions
    register_runtime_routes(application, module_supervisor)

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

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

    @application.post("/api/v1/sessions/{session_id}/emergency-stop")
    async def emergency_stop_session(session_id: str) -> SessionResponse:
        try:
            return SessionResponse.from_snapshot(
                await work_sessions.emergency_stop(session_id)
            )
        except SessionNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

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
