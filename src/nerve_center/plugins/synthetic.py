"""Synthetic plugin used to prove the generic runner."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from nerve_center.domain.task import TaskContext, TaskResult, TaskStatus


class SyntheticTaskPlugin:
    plugin_id = "synthetic"
    display_name = "Synthetic Validation Task"

    async def run(self, context: TaskContext) -> TaskResult:
        iterations = max(0, int(context.configuration.get("iterations", 3)))
        delay_ms = max(0, int(context.configuration.get("delay_ms", 0)))
        completed = int(context.checkpoint.get("completed", 0))

        while completed < iterations:
            if context.cancellation_requested():
                return TaskResult(
                    status=TaskStatus.CANCELLED,
                    summary="Synthetic task cancelled; checkpoint preserved.",
                    metrics={"completed": completed, "requested": iterations},
                )
            if datetime.now(UTC) >= context.deadline:
                return TaskResult(
                    status=TaskStatus.PARTIAL,
                    summary="Synthetic task reached the run deadline.",
                    metrics={"completed": completed, "requested": iterations},
                )
            if delay_ms:
                await asyncio.sleep(delay_ms / 1000)
            completed += 1
            context.save_checkpoint({"completed": completed})

        return TaskResult(
            status=TaskStatus.SUCCEEDED,
            summary="Synthetic task completed.",
            metrics={"completed": completed, "requested": iterations},
        )
