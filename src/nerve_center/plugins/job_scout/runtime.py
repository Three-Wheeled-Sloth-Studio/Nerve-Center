"""Manager-side scoped operation bridge for the Job Scout worker."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from nerve_center.discovery.models import DiscoverySource
from nerve_center.discovery.service import DiscoveryService
from nerve_center.persistence.discovery import DiscoverySourceRepository


class JobScoutOperationBridge:
    def __init__(
        self,
        service: DiscoveryService,
        sources: DiscoverySourceRepository,
    ) -> None:
        self.service = service
        self.sources = sources

    async def invoke(self, operation: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        if operation == "list_due_sources":
            due_sources: list[DiscoverySource] = list(self.sources.list_due())
            return {"source_ids": [item.id for item in due_sources]}
        if operation == "scan_source":
            source_id = str(payload.get("source_id", ""))
            if not source_id:
                raise ValueError("scan_source requires source_id")
            result = await self.service.scan_source(source_id)
            return {
                "status": result.status.value,
                "openings_found": len(result.openings),
                "requests_made": result.requests_made,
            }
        raise ValueError(f"unsupported Job Scout operation {operation!r}")
