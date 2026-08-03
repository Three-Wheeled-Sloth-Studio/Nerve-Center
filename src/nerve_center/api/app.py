"""Minimal local API bootstrap."""

from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

import uvicorn
from fastapi import FastAPI

from nerve_center import __version__
from nerve_center.config import Settings
from nerve_center.persistence.database import Database

settings = Settings()
database = Database(settings)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    database.initialize()
    yield


app = FastAPI(title="Nerve Center", version=__version__, lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


def run() -> None:
    uvicorn.run("nerve_center.api.app:app", host=settings.host, port=settings.port, reload=False)
