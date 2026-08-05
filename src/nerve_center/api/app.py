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
from nerve_center.plugins.job_scout.bootstrap import install_job_scout
from nerve_center.plugins.synthetic import SyntheticTaskPlugin
from nerve_center.providers.base import StructuredProvider
from nerve_center.scheduler.registry import TaskRegistry
from nerve_center.scheduler.runner import RunnerService
from nerve_center.scheduler.service import SchedulerService

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
    registry = TaskRegistry()
    registry.register(SyntheticTaskPlugin())
    runner = RunnerService(
        repository,
        registry,
        module_lifecycle=lambda module_id: module_repository.get(module_id).lifecycle_state,
    )
    scheduler = SchedulerService(
        repository,
        runner,
        poll_seconds=runtime_settings.scheduler_poll_seconds,
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        database.initialize()
        module_repository.synchronize(registry.list_modules())
        runner.recover_interrupted()
        await scheduler.start()
        yield
        await scheduler.stop()
        await runner.shutdown()

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
    application.state.runner = runner
    application.state.scheduler = scheduler
    application.state.module_repository = module_repository
    job_scout = install_job_scout(
        application,
        database,
        runtime_settings,
        provider,
    )
    registry.register_module(job_scout.manifest, job_scout.task_plugins)

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @application.get("/api/v1/modules")
    def list_modules() -> list[ModuleResponse]:
        return [ModuleResponse.from_installed(item) for item in module_repository.list()]

    @application.get("/api/v1/modules/{module_id}")
    def get_module(module_id: str) -> ModuleResponse:
        try:
            return ModuleResponse.from_installed(module_repository.get(module_id))
        except ModuleNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @application.patch("/api/v1/modules/{module_id}")
    def update_module(
        module_id: str,
        request: ModuleLifecycleRequest,
    ) -> ModuleResponse:
        try:
            return ModuleResponse.from_installed(
                module_repository.set_lifecycle(module_id, request.lifecycle_state)
            )
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
