"""Narrow manager-operation bridge exposed to the Code Shop worker."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from nerve_center.code_shop.domain import EngineeringCapability
from nerve_center.code_shop.service import CodeShopService


class CodeShopOperationBridge:
    def __init__(self, service: CodeShopService) -> None:
        self.service = service

    async def invoke(self, operation: str, payload: dict[str, Any]) -> dict[str, Any]:
        if operation == "overview":
            return self.service.overview()
        if operation == "submit_capability":
            if "model" in payload or "provider" in payload:
                raise ValueError("Code Shop capability requests are model-blind")
            task = self.service.create_task(
                str(payload["repository_id"]),
                title=str(payload["title"]),
                capability=EngineeringCapability(str(payload["capability"])),
                source_backlog=dict(payload.get("source_backlog") or {}),
            )
            return asdict(task)
        raise KeyError(f"unsupported Code Shop operation {operation!r}")
