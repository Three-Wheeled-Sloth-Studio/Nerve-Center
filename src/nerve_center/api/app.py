"""Minimal local API bootstrap."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from nerve_center import __version__
from nerve_center.config import Settings
from nerve_center.persistence.database import Database


def create_app(settings: Settings | None = None) -> FastAPI:
    runtime_settings = settings or Settings()
    database = Database(runtime_settings)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        database.initialize()
        yield

    application = FastAPI(title="Nerve Center", version=__version__, lifespan=lifespan)

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

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
