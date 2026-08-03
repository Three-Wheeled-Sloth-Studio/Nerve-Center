"""Job Scout discovery task plugin for the generic scheduler."""

from __future__ import annotations

from datetime import UTC, datetime

from nerve_center.discovery.models import ScanStatus
from nerve_center.discovery.service import DiscoveryService
from nerve_center.domain.task import TaskContext, TaskResult, TaskStatus
from nerve_center.persistence.discovery import DiscoverySourceRepository


class JobDiscoveryTaskPlugin:
    plugin_id = "job_scout.discovery"
    display_name = "Job Scout Discovery"

    def __init__(
        self,
        service: DiscoveryService,
        sources: DiscoverySourceRepository,
    ) -> None:
        self.service = service
        self.sources = sources

    async def run(self, context: TaskContext) -> TaskResult:
        configured = context.configuration.get("source_ids")
        if isinstance(configured, list):
            source_ids = [str(item) for item in configured]
        else:
            source_ids = [item.id for item in self.sources.list_due()]
        completed = [
            str(item) for item in context.checkpoint.get("completed_source_ids", [])
        ]
        remaining = [item for item in source_ids if item not in completed]
        openings_found = 0
        failed_sources = 0

        for source_id in remaining:
            if context.cancellation_requested():
                return TaskResult(
                    status=TaskStatus.CANCELLED,
                    summary="Job discovery was cancelled.",
                    metrics={
                        "sources_completed": len(completed),
                        "openings_found": openings_found,
                    },
                )
            if datetime.now(UTC) >= context.deadline:
                return TaskResult(
                    status=TaskStatus.PARTIAL,
                    summary="Job discovery reached its run deadline.",
                    metrics={
                        "sources_completed": len(completed),
                        "openings_found": openings_found,
                    },
                )
            context.save_checkpoint(
                {
                    "completed_source_ids": completed,
                    "active_source_id": source_id,
                    "openings_found": openings_found,
                }
            )
            async with context.resources.work_slot():
                result = await self.service.scan_source(
                    source_id,
                    before_request=context.resources.consume_request,
                )
            openings_found += len(result.openings)
            if result.status not in {ScanStatus.SUCCEEDED, ScanStatus.PARTIAL}:
                failed_sources += 1
            completed.append(source_id)
            context.save_checkpoint(
                {
                    "completed_source_ids": completed,
                    "active_source_id": None,
                    "last_source_id": source_id,
                    "openings_found": openings_found,
                }
            )

        status = TaskStatus.PARTIAL if failed_sources else TaskStatus.SUCCEEDED
        return TaskResult(
            status=status,
            summary=(
                f"Scanned {len(completed)} sources and found {openings_found} openings."
            ),
            metrics={
                "sources_completed": len(completed),
                "failed_sources": failed_sources,
                "openings_found": openings_found,
            },
        )
