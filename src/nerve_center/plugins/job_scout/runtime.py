"""Manager-side scoped operation bridge for the Job Scout worker."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from nerve_center.discovery.models import DiscoverySource
from nerve_center.discovery.service import DiscoveryService
from nerve_center.persistence.discovery import DiscoverySourceRepository
from nerve_center.plugins.job_scout.configuration import (
    JobScoutCoordinator,
    JobScoutScanRequest,
)
from nerve_center.plugins.job_scout.discovery_learning import JobScoutDiscoveryRepository


class JobScoutOperationBridge:
    def __init__(
        self,
        service: DiscoveryService,
        sources: DiscoverySourceRepository,
        coordinator: JobScoutCoordinator,
        learning: JobScoutDiscoveryRepository,
    ) -> None:
        self.service = service
        self.sources = sources
        self.coordinator = coordinator
        self.learning = learning

    async def invoke(self, operation: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        if operation == "scheduled_scan":
            result = await self.coordinator.scan(JobScoutScanRequest(due_only=True))
            return {
                "sources_scanned": result.sources_scanned,
                "sources_completed": result.sources_scanned,
                "openings_found": result.openings_found,
                "warning_count": len(result.warnings),
                "request_count": len(result.queries_run)
                + sum(scan.requests_made for scan in result.scans),
            }
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
