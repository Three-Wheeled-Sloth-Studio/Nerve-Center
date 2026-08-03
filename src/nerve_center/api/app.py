"""Local API bootstrap and run-control surface."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

import uvicorn
from fastapi import FastAPI, HTTPException, Query, status

from nerve_center import __version__
from nerve_center.api.schemas import RunCreateRequest, RunEventResponse, RunResponse
from nerve_center.config import Settings
from nerve_center.domain.run import (
    InvalidRunTransitionError,
    RunNotFoundError,
    RunNotReadyError,
)
from nerve_center.persistence.database import Database
from nerve_center.persistence.runs import RunRepository
from nerve_center.plugins.synthetic import SyntheticTaskPlugin
from nerve_center.profile.api import register_profile_routes
from nerve_center.providers.base import StructuredProvider
from nerve_center.scheduler.registry import TaskRegistry
from nerve_center.scheduler.runner import RunnerService
from nerve_center.scheduler.service import SchedulerService


def create_app(
    settings: Settings | None = None,
    provider: StructuredProvider | None = None,
) -> FastAPI:
    runtime_settings = settings or Settings()
    database = Database(runtime_settings)
    repository = RunRepository(database)
    registry = TaskRegistry()
    registry.register(SyntheticTaskPlugin())
    runner = RunnerService(repository, registry)
    scheduler = SchedulerService(
        repository,
        runner,
        poll_seconds=runtime_settings.scheduler_poll_seconds,
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        database.initialize()
        runner.recover_interrupted()
        await scheduler.start()
        yield
        await scheduler.stop()
        await runner.shutdown()

    application = FastAPI(title="Nerve Center", version=__version__, lifespan=lifespan)
    application.state.repository = repository
    application.state.runner = runner
    application.state.scheduler = scheduler
    register_profile_routes(application, database, runtime_settings, provider)

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @application.post("/api/v1/runs", status_code=status.HTTP_201_CREATED)
    def create_run(request: RunCreateRequest) -> RunResponse:
        try:
            registry.get(request.task_id)
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
        "nerve_center.api.app:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )
