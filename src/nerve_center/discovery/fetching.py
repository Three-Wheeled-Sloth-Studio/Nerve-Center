"""Shared low-concurrency HTTP acquisition with challenge and throttle detection."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx

_CHALLENGE_MARKERS = (
    "captcha",
    "unusual traffic",
    "verify you are human",
    "checking your browser",
    "cloudflare ray id",
    "access denied",
    "security challenge",
)


@dataclass(frozen=True, slots=True)
class FetchResponse:
    url: str
    status_code: int
    text: str
    headers: dict[str, str]
    challenged: bool
    throttled: bool


class DomainRequestGate:
    def __init__(self, max_per_domain: int = 1) -> None:
        if max_per_domain < 1:
            raise ValueError("max_per_domain must be at least 1")
        self.max_per_domain = max_per_domain
        self._gates: dict[str, asyncio.Semaphore] = {}
        self._lock = asyncio.Lock()

    async def for_url(self, url: str) -> asyncio.Semaphore:
        domain = (urlsplit(url).hostname or "").casefold()
        async with self._lock:
            return self._gates.setdefault(domain, asyncio.Semaphore(self.max_per_domain))


class HttpFetcher:
    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 30.0,
        gate: DomainRequestGate | None = None,
        before_request: Callable[[], object] | None = None,
    ) -> None:
        self._client = client
        self.timeout_seconds = timeout_seconds
        self.gate = gate or DomainRequestGate(1)
        self.before_request = before_request

    async def get(
        self,
        url: str,
        *,
        params: dict[str, object] | None = None,
        headers: dict[str, str] | None = None,
    ) -> FetchResponse:
        if self.before_request is not None:
            self.before_request()
        semaphore = await self.gate.for_url(url)
        request_headers = {
            "Accept": (
                "application/json,text/html,application/xhtml+xml,"
                "application/xml;q=0.9,*/*;q=0.8"
            ),
            "User-Agent": "Nerve-Center-Job-Scout/0.3 (+public-source-discovery)",
            **(headers or {}),
        }
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(
            timeout=self.timeout_seconds,
            follow_redirects=True,
        )
        try:
            async with semaphore:
                response = await client.get(url, params=params, headers=request_headers)
        finally:
            if owns_client:
                await client.aclose()
        text = response.text
        lowered = text[:200_000].casefold()
        challenged = response.status_code in {401, 403} and any(
            marker in lowered for marker in _CHALLENGE_MARKERS
        )
        if not challenged:
            challenged = any(marker in lowered for marker in _CHALLENGE_MARKERS)
        return FetchResponse(
            url=str(response.url),
            status_code=response.status_code,
            text=text,
            headers={key.casefold(): value for key, value in response.headers.items()},
            challenged=challenged,
            throttled=response.status_code == 429,
        )
