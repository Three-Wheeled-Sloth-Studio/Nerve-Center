"""Manager-side scoped operation bridge for the Job Scout worker."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict
from typing import Any

from nerve_center.discovery.models import DiscoverySource
from nerve_center.discovery.service import DiscoveryService
from nerve_center.persistence.discovery import DiscoverySourceRepository
from nerve_center.plugins.job_scout.configuration import (
    JobScoutCoordinator,
    JobScoutScanRequest,
)
from nerve_center.plugins.job_scout.discovery_learning import JobScoutDiscoveryRepository
from nerve_center.plugins.job_scout.discovery_loop import JobScoutDiscoveryLoop


class JobScoutOperationBridge:
    def __init__(
        self,
        service: DiscoveryService,
        sources: DiscoverySourceRepository,
        coordinator: JobScoutCoordinator,
        learning: JobScoutDiscoveryRepository,
        discovery_loop: JobScoutDiscoveryLoop,
    ) -> None:
        self.service = service
        self.sources = sources
        self.coordinator = coordinator
        self.learning = learning
        self.discovery_loop = discovery_loop

    async def invoke(self, operation: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        if operation == "discovery_readiness":
            configuration = self.coordinator.store.load()
            keywords = self.coordinator._discover_keywords(configuration).keywords
            durable_market = bool(self.service.companies.list() or self.sources.list())
            configured_seed = bool(
                configuration.target_titles
                or configuration.manual_keywords
                or configuration.locations
                or configuration.source_urls
                or configuration.source_ids
                or keywords
            )
            return {
                "ready": configured_seed or durable_market,
                "configured_seed": configured_seed,
                "durable_market": durable_market,
            }
        if operation == "prepare_discovery":
            return await self.discovery_loop.prepare(_required_string(payload, "run_id"))
        if operation == "discovery_cycle":
            summary = await self.discovery_loop.cycle(
                _required_string(payload, "run_id"),
                int(payload.get("cycle", 0)),
            )
            return asdict(summary)
        if operation == "deterministic_reflection":
            return self.discovery_loop.deterministic_reflection(
                _required_string(payload, "run_id"),
                int(payload.get("cycle", 0)),
            )
        if operation == "reflection_work_request":
            return self.discovery_loop.reflection_work_request(
                _required_string(payload, "run_id"),
                int(payload.get("cycle", 0)),
            )
        if operation == "record_reflection_request":
            request_id = _required_string(payload, "request_id")
            self.learning.record_reflection_request(
                request_id,
                _required_string(payload, "run_id"),
                int(payload.get("cycle", 0)),
            )
            return {"request_id": request_id, "recorded": True}
        if operation == "apply_reflection_result":
            request_id = _required_string(payload, "request_id")
            known = self.learning.reflection_request(request_id)
            if known is None:
                return {"recognized": False, "strategies_added": 0}
            value = payload.get("value")
            if not isinstance(value, dict):
                raise ValueError("reflection result value must be an object")
            created = self.discovery_loop.apply_reflection_result(request_id, value)
            return {"recognized": True, "strategies_added": created}
        if operation == "discovery_summary":
            return self.discovery_loop.summary(_required_string(payload, "run_id"))
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


def _required_string(payload: Mapping[str, Any], field: str) -> str:
    value = str(payload.get(field, "")).strip()
    if not value:
        raise ValueError(f"{field} is required")
    return value
