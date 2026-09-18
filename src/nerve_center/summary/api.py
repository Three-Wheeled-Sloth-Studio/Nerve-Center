"""Read-only manager summary API."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Query

from nerve_center.summary.service import SummaryService


def register_summary_routes(application: FastAPI, service: SummaryService) -> None:
    @application.get("/api/v1/summary")
    def summary(
        starts_at: datetime = Query(...),
        ends_at: datetime = Query(...),
    ) -> dict[str, Any]:
        try:
            return asdict(service.snapshot(starts_at, ends_at))
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
