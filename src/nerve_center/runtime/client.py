"""Small HTTP client used by managed module workers."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any, cast

import httpx


class ModuleRuntimeClient:
    def __init__(self, endpoint: str, module_id: str, token: str) -> None:
        self.base_url = f"{endpoint.rstrip('/')}/runtime/v1/modules/{module_id}"
        self.headers = {"Authorization": f"Bearer {token}"}
        self.client = httpx.AsyncClient(timeout=60.0, headers=self.headers)

    async def close(self) -> None:
        await self.client.aclose()

    async def heartbeat(self, status: str, activity: str, **metrics: Any) -> None:
        await self._request(
            "POST", "/heartbeat", json={"status": status, "activity": activity, **metrics}
        )

    async def next_work(self) -> dict[str, Any] | None:
        response = await self._request("GET", "/work")
        return cast(dict[str, Any] | None, response.json())

    async def module_control(self) -> dict[str, bool]:
        return cast(dict[str, bool], (await self._request("GET", "/control")).json())

    async def control(self, run_id: str) -> dict[str, Any]:
        return cast(
            dict[str, Any],
            (await self._request("GET", f"/runs/{run_id}/control")).json(),
        )

    async def checkpoint(self, run_id: str, value: Mapping[str, Any]) -> None:
        await self._request(
            "POST", f"/runs/{run_id}/checkpoint", json={"value": dict(value)}
        )

    async def consume(self, run_id: str, resource: str, count: int = 1) -> None:
        await self._request(
            "POST",
            f"/runs/{run_id}/resources",
            json={"resource": resource, "count": count},
        )

    async def invoke(
        self, run_id: str, operation: str, payload: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        return cast(
            dict[str, Any],
            (
                await self._request(
                "POST",
                f"/runs/{run_id}/operations",
                json={"operation": operation, "payload": dict(payload or {})},
                )
            ).json(),
        )

    async def complete(
        self,
        run_id: str,
        status: str,
        summary: str,
        metrics: Mapping[str, int | float | str | bool],
    ) -> None:
        await self._request(
            "POST",
            f"/runs/{run_id}/complete",
            json={"status": status, "summary": summary, "metrics": dict(metrics)},
        )

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(20):
            try:
                response = await self.client.request(method, f"{self.base_url}{path}", **kwargs)
                response.raise_for_status()
                return response
            except (httpx.ConnectError, httpx.ConnectTimeout) as error:
                last_error = error
                if attempt == 19:
                    break
                await asyncio.sleep(0.25)
        raise RuntimeError("manager runtime endpoint is unavailable") from last_error
