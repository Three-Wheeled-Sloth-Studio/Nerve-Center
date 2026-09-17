from __future__ import annotations

import asyncio
from datetime import timedelta

import httpx
import pytest

from nerve_center.discovery.fetching import DomainRequestGate, HttpFetcher
from nerve_center.discovery.search import (
    PublicWebSearchAdapter,
    SearchChallengeError,
    normalize_public_search_result_url,
)


class MemorySearchCache:
    def __init__(self) -> None:
        self.values: dict[tuple[str, str], dict[str, object]] = {}

    def get(self, provider: str, query: str, now: object | None = None) -> dict[str, object] | None:
        del now
        value = self.values.get((provider, query))
        return dict(value) if value is not None else None

    def put(
        self,
        provider: str,
        query: str,
        payload: dict[str, object],
        *,
        ttl: timedelta = timedelta(days=7),
        now: object | None = None,
    ) -> None:
        del ttl, now
        self.values[(provider, query)] = dict(payload)


def _fetcher(handler: object) -> tuple[HttpFetcher, httpx.AsyncClient]:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return (
        HttpFetcher(
            client=client,
            gate=DomainRequestGate(1, minimum_interval_seconds=0.0),
        ),
        client,
    )


def test_public_search_rotates_to_bing_after_duckduckgo_challenge() -> None:
    cache = MemorySearchCache()
    primary_hosts: list[str] = []

    def challenge_handler(request: httpx.Request) -> httpx.Response:
        primary_hosts.append(request.url.host)
        return httpx.Response(
            200,
            text=(
                "<html><body>Unfortunately, bots use DuckDuckGo too. "
                "Please complete the following challenge.</body></html>"
            ),
            request=request,
        )

    fetcher, client = _fetcher(challenge_handler)
    adapter = PublicWebSearchAdapter(cache, fetcher=fetcher, max_results=5)  # type: ignore[arg-type]
    with pytest.raises(SearchChallengeError):
        asyncio.run(adapter.search_references("first employer query"))
    asyncio.run(client.aclose())

    assert primary_hosts == ["html.duckduckgo.com"]
    assert adapter.last_provider == "duckduckgo_html"
    assert adapter.last_provider_fallback_used is False
    assert cache.get("public_search_provider_health:v1", "duckduckgo_html") is not None

    fallback_hosts: list[str] = []

    def bing_handler(request: httpx.Request) -> httpx.Response:
        fallback_hosts.append(request.url.host)
        return httpx.Response(
            200,
            text=(
                '<html><body><ol><li class="b_algo"><h2>'
                '<a href="https://example.com/careers">Example Careers</a>'
                "</h2></li></ol></body></html>"
            ),
            request=request,
        )

    fallback_fetcher, fallback_client = _fetcher(bing_handler)
    fresh_adapter = PublicWebSearchAdapter(  # type: ignore[arg-type]
        cache,
        fetcher=fallback_fetcher,
        max_results=5,
    )
    results = asyncio.run(fresh_adapter.search_references("second employer query"))
    asyncio.run(fallback_client.aclose())

    assert fallback_hosts == ["www.bing.com"]
    assert fresh_adapter.last_provider == "bing_html"
    assert fresh_adapter.last_provider_fallback_used is True
    assert [item.url for item in results] == ["https://example.com/careers"]


def test_ordinary_empty_duckduckgo_result_does_not_rotate_provider() -> None:
    cache = MemorySearchCache()
    hosts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        hosts.append(request.url.host)
        return httpx.Response(
            200,
            text="<html><body>No results found for this search.</body></html>",
            request=request,
        )

    fetcher, client = _fetcher(handler)
    adapter = PublicWebSearchAdapter(cache, fetcher=fetcher, max_results=5)  # type: ignore[arg-type]
    assert asyncio.run(adapter.search_references("first empty query")) == []
    assert asyncio.run(adapter.search_references("second empty query")) == []
    asyncio.run(client.aclose())

    assert hosts == ["html.duckduckgo.com", "html.duckduckgo.com"]
    assert adapter.last_provider == "duckduckgo_html"
    assert adapter.last_provider_fallback_used is False


def test_bing_tracking_redirect_is_normalized_to_public_target() -> None:
    encoded = "aHR0cHM6Ly9leGFtcGxlLmNvbS9jYXJlZXJz"
    value = f"https://www.bing.com/ck/a?u=a1{encoded}"
    assert normalize_public_search_result_url(value) == "https://example.com/careers"
