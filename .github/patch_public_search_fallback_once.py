from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"expected patch anchor not found in {path}: {old[:80]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_block(path: str, start_marker: str, end_marker: str, replacement: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    target.write_text(text[:start] + replacement + text[end:], encoding="utf-8")


(ROOT / "src/nerve_center/discovery/public_search_fallback.py").write_text(
    '''"""Bounded parsers for ordinary-public search fallback transports."""

from __future__ import annotations

from html.parser import HTMLParser


class BingSearchResultParser(HTMLParser):
    """Capture result-title links from Bing's public HTML result list only."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.anchors: list[tuple[str, str]] = []
        self._result_li_depth = 0
        self._in_heading = False
        self._href: str | None = None
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "li":
            classes = set((values.get("class") or "").split())
            if self._result_li_depth:
                self._result_li_depth += 1
            elif "b_algo" in classes:
                self._result_li_depth = 1
            return
        if not self._result_li_depth:
            return
        if tag == "h2":
            self._in_heading = True
            return
        if tag == "a" and self._in_heading and self._href is None:
            href = values.get("href")
            if href:
                self._href = href
                self._parts = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href is not None:
            title = " ".join("".join(self._parts).split())
            if title:
                self.anchors.append((self._href, title))
            self._href = None
            self._parts = []
            return
        if not self._result_li_depth:
            return
        if tag == "h2":
            self._in_heading = False
        elif tag == "li":
            self._result_li_depth -= 1
            if self._result_li_depth == 0:
                self._in_heading = False
                self._href = None
                self._parts = []
''',
    encoding="utf-8",
)

replace_once(
    "src/nerve_center/discovery/search.py",
    "from nerve_center.discovery.normalization import canonicalize_url, has_job_route_evidence\n",
    "from nerve_center.discovery.normalization import canonicalize_url, has_job_route_evidence\n"
    "from nerve_center.discovery.public_search_fallback import BingSearchResultParser\n",
)
replace_once(
    "src/nerve_center/discovery/search.py",
    '    provider = "duckduckgo_html"\n',
    '    provider = "duckduckgo_html"\n'
    '    fallback_provider = "bing_html"\n'
    '    provider_health_cache = "public_search_provider_health:v1"\n',
)
replace_once(
    "src/nerve_center/discovery/search.py",
    "        self.max_results = max_results\n        self._cooldown_messages: dict[str, str] = {}\n",
    "        self.max_results = max_results\n"
    "        self._cooldown_messages: dict[str, str] = {}\n"
    "        self.last_provider = \"\"\n"
    "        self.last_provider_fallback_used = False\n",
)

NEW_SEARCH_BLOCK = '''    def _provider_cache_name(self, provider: str, result_scope: str) -> str:\n        return f"{provider}:{self.max_results}:{result_scope}"\n\n    def _provider_cooldown_message(self, provider: str) -> str | None:\n        message = self._cooldown_messages.get(provider)\n        if message:\n            return message\n        cached = self.cache.get(self.provider_health_cache, provider)\n        if cached is None or cached.get("status") != "challenged":\n            return None\n        message = str(\n            cached.get("message")\n            or "The public search provider is cooling down after a challenge."\n        )\n        self._cooldown_messages[provider] = message\n        return message\n\n    def _mark_provider_cooldown(self, provider: str, message: str) -> None:\n        self._cooldown_messages[provider] = message\n        self.cache.put(\n            self.provider_health_cache,\n            provider,\n            {"status": "challenged", "message": message},\n            ttl=timedelta(hours=1),\n        )\n\n    def _select_public_provider(\n        self,\n        query: str,\n        result_scope: str,\n    ) -> tuple[str, str, dict[str, object] | None]:\n        cooldowns: list[str] = []\n        for provider in (self.provider, self.fallback_provider):\n            cache_provider = self._provider_cache_name(provider, result_scope)\n            cached = self.cache.get(cache_provider, query)\n            cached_succeeded = cached is not None and cached.get("status") == "succeeded"\n            cached_results = cached.get("results", []) if cached_succeeded else []\n            if cached_succeeded and isinstance(cached_results, list) and cached_results:\n                return provider, cache_provider, cached\n            cooldown = self._provider_cooldown_message(provider)\n            if cooldown:\n                cooldowns.append(cooldown)\n                continue\n            if cached is not None and cached.get("status") == "challenged":\n                message = str(\n                    cached.get("message")\n                    or "The public search provider is cooling down after a challenge."\n                )\n                self._mark_provider_cooldown(provider, message)\n                cooldowns.append(message)\n                continue\n            return provider, cache_provider, cached\n        raise SearchChallengeError(\n            cooldowns[-1]\n            if cooldowns\n            else "Public search providers are temporarily cooling down."\n        )\n\n    async def _search(\n        self,\n        query: str,\n        *,\n        include_other: bool,\n    ) -> list[SearchResult]:\n        builtin_query = _board_native_query(query, "builtin.com")\n        result_scope = "references" if include_other else "hiring"\n        if builtin_query is not None:\n            provider = "builtin_html"\n            self.last_provider = provider\n            self.last_provider_fallback_used = False\n            if provider in self._cooldown_messages:\n                raise SearchChallengeError(self._cooldown_messages[provider])\n            cache_provider = self._provider_cache_name(provider, result_scope)\n            cached = self.cache.get(cache_provider, query)\n            if cached is not None and cached.get("status") == "challenged":\n                raise SearchChallengeError(\n                    str(\n                        cached.get("message")\n                        or "Public search is cooling down after a challenge."\n                    )\n                )\n        else:\n            provider, cache_provider, cached = self._select_public_provider(\n                query, result_scope\n            )\n            self.last_provider = provider\n            self.last_provider_fallback_used = provider == self.fallback_provider\n\n        if cached is not None and cached.get("status") == "succeeded":\n            return _rehydrate_cached_results(\n                cached.get("results", []),\n                include_other=include_other,\n            )\n\n        if builtin_query is not None:\n            search_url = "https://builtin.com/jobs"\n            params = _builtin_search_params(builtin_query)\n        elif provider == self.fallback_provider:\n            search_url = "https://www.bing.com/search"\n            params = {"q": query, "count": str(self.max_results)}\n        else:\n            search_url = "https://html.duckduckgo.com/html/"\n            params = {"q": query, "source": "web"}\n        try:\n            response = await self.fetcher.get(\n                search_url,\n                params=params,\n                headers={"Accept": "text/html,application/xhtml+xml"},\n            )\n        except httpx.RequestError as error:\n            raise RuntimeError("The public search provider could not be reached.") from error\n        if response.challenged or response.throttled or response.status_code in {401, 403, 429}:\n            message = "The public search provider requested a cooldown; try the scan again later."\n            if provider in {self.provider, self.fallback_provider}:\n                self._mark_provider_cooldown(provider, message)\n            else:\n                self._cooldown_messages[provider] = message\n            self.cache.put(\n                cache_provider,\n                query,\n                {"status": "challenged", "message": message},\n                ttl=timedelta(hours=1),\n            )\n            raise SearchChallengeError(message)\n        if response.status_code >= 400:\n            raise RuntimeError(f"Public search failed with HTTP {response.status_code}.")\n\n        if provider == self.fallback_provider:\n            parser = BingSearchResultParser()\n        else:\n            parser = _PublicSearchResultParser()\n        parser.feed(response.text)\n        parser.close()\n        results: list[SearchResult] = []\n        seen: set[str] = set()\n        for href, title in parser.anchors:\n            if builtin_query is not None and href.startswith("/"):\n                href = f"https://builtin.com{href}"\n            url = normalize_public_search_result_url(href)\n            if not url or not title or url in seen:\n                continue\n            if builtin_query is not None:\n                split = urlsplit(url)\n                if (split.hostname or "").casefold().removeprefix("www.") != "builtin.com":\n                    continue\n                if not split.path.casefold().startswith("/job/"):\n                    continue\n            classification = classify_discovered_url(url)\n            if classification is UrlClassification.OTHER and not include_other:\n                continue\n            seen.add(url)\n            results.append(\n                SearchResult(\n                    title=title[:300],\n                    url=url,\n                    classification=classification,\n                    domain=(urlsplit(url).hostname or "").removeprefix("www."),\n                )\n            )\n            if len(results) >= self.max_results:\n                break\n        self.cache.put(\n            cache_provider,\n            query,\n            {\n                "status": "succeeded",\n                "results": [item.model_dump(mode="json") for item in results],\n            },\n            ttl=timedelta(days=1),\n        )\n        return results\n'''
replace_block(
    "src/nerve_center/discovery/search.py",
    "    async def _search(\n",
    "\n\ndef _board_native_query",
    NEW_SEARCH_BLOCK,
)

NEW_NORMALIZER = '''def normalize_public_search_result_url(value: str) -> str | None:\n    if not value:\n        return None\n    if value.startswith("//"):\n        value = f"https:{value}"\n    split = urlsplit(value)\n    hostname = (split.hostname or "").casefold().removeprefix("www.")\n    if hostname == "duckduckgo.com" and split.path == "/l/":\n        values = parse_qs(split.query).get("uddg")\n        value = values[0] if values else ""\n        split = urlsplit(value)\n        hostname = (split.hostname or "").casefold().removeprefix("www.")\n    if (hostname == "bing.com" or hostname.endswith(".bing.com")) and split.path == "/ck/a":\n        values = parse_qs(split.query).get("u")\n        candidate = values[0] if values else ""\n        if candidate.startswith(("http://", "https://")):\n            value = candidate\n        elif candidate.startswith("a1"):\n            encoded = candidate[2:]\n            encoded += "=" * (-len(encoded) % 4)\n            try:\n                value = base64.urlsafe_b64decode(encoded).decode("utf-8")\n            except (ValueError, UnicodeDecodeError):\n                value = ""\n        else:\n            value = ""\n        split = urlsplit(value)\n        hostname = (split.hostname or "").casefold().removeprefix("www.")\n    if split.scheme not in {"http", "https"}:\n        return None\n    if (\n        hostname in {"search.brave.com", "brave.com", "duckduckgo.com", "bing.com"}\n        or hostname.endswith(".bing.com")\n    ):\n        return None\n    return canonicalize_url(value)\n'''
replace_block(
    "src/nerve_center/discovery/search.py",
    "def normalize_public_search_result_url(value: str) -> str | None:\n",
    "\n\ndef classify_discovered_url",
    NEW_NORMALIZER,
)

replace_once(
    "src/nerve_center/plugins/job_scout/discovery_learning.py",
    '    "search_requests_failed": 0,\n',
    '    "search_requests_failed": 0,\n    "search_provider_fallbacks": 0,\n',
)
replace_once(
    "src/nerve_center/plugins/job_scout/discovery_loop.py",
    '            "search_requests_failed": 0,\n',
    '            "search_requests_failed": 0,\n            "search_provider_fallbacks": 0,\n',
)
replace_once(
    "src/nerve_center/plugins/job_scout/discovery_loop.py",
    '                    "search_requests_failed",\n                    "search_results_returned",\n',
    '                    "search_requests_failed",\n                    "search_provider_fallbacks",\n                    "search_results_returned",\n',
)
replace_once(
    "src/nerve_center/plugins/job_scout/discovery_loop.py",
    '        warnings: list[str] = []\n        try:\n',
    '        warnings: list[str] = []\n        search_provider = ""\n        search_provider_fallback_used = False\n        try:\n',
)
replace_once(
    "src/nerve_center/plugins/job_scout/discovery_loop.py",
    '            results = await search(query)\n',
    '            results = await search(query)\n'
    '            search_provider = str(getattr(self.search_adapter, "last_provider", "") or "")\n'
    '            search_provider_fallback_used = bool(\n'
    '                getattr(self.search_adapter, "last_provider_fallback_used", False)\n'
    '            )\n',
)
replace_once(
    "src/nerve_center/plugins/job_scout/discovery_loop.py",
    '        except SearchChallengeError as error:\n            return (\n',
    '        except SearchChallengeError as error:\n'
    '            search_provider = str(getattr(self.search_adapter, "last_provider", "") or "")\n'
    '            search_provider_fallback_used = bool(\n'
    '                getattr(self.search_adapter, "last_provider_fallback_used", False)\n'
    '            )\n'
    '            return (\n',
)
replace_once(
    "src/nerve_center/plugins/job_scout/discovery_loop.py",
    '                        "query": query,\n                        "stages": {"search_requests_failed": 1},\n',
    '                        "query": query,\n'
    '                        "search_provider": search_provider,\n'
    '                        "search_provider_fallback_used": search_provider_fallback_used,\n'
    '                        "stages": {\n'
    '                            "search_requests_failed": 1,\n'
    '                            "search_provider_fallbacks": int(search_provider_fallback_used),\n'
    '                        },\n',
)
replace_once(
    "src/nerve_center/plugins/job_scout/discovery_loop.py",
    '        except RuntimeError as error:\n            return (\n',
    '        except RuntimeError as error:\n'
    '            search_provider = str(getattr(self.search_adapter, "last_provider", "") or "")\n'
    '            search_provider_fallback_used = bool(\n'
    '                getattr(self.search_adapter, "last_provider_fallback_used", False)\n'
    '            )\n'
    '            return (\n',
)
replace_once(
    "src/nerve_center/plugins/job_scout/discovery_loop.py",
    '                        "query": query,\n                        "stages": {"search_requests_failed": 1},\n',
    '                        "query": query,\n'
    '                        "search_provider": search_provider,\n'
    '                        "search_provider_fallback_used": search_provider_fallback_used,\n'
    '                        "stages": {\n'
    '                            "search_requests_failed": 1,\n'
    '                            "search_provider_fallbacks": int(search_provider_fallback_used),\n'
    '                        },\n',
)
replace_once(
    "src/nerve_center/plugins/job_scout/discovery_loop.py",
    '                        "query": query,\n                        "regional_alias_evidence": evidence,\n',
    '                        "query": query,\n'
    '                        "search_provider": search_provider,\n'
    '                        "search_provider_fallback_used": search_provider_fallback_used,\n'
    '                        "regional_alias_evidence": evidence,\n',
)
replace_once(
    "src/nerve_center/plugins/job_scout/discovery_loop.py",
    '                            "search_requests_completed": 1,\n                            "search_results_returned": len(results),\n',
    '                            "search_requests_completed": 1,\n'
    '                            "search_provider_fallbacks": int(search_provider_fallback_used),\n'
    '                            "search_results_returned": len(results),\n',
)
replace_once(
    "src/nerve_center/plugins/job_scout/discovery_loop.py",
    '                    "query": query,\n                    "stages": {\n                        "search_requests_completed": 1,\n',
    '                    "query": query,\n'
    '                    "search_provider": search_provider,\n'
    '                    "search_provider_fallback_used": search_provider_fallback_used,\n'
    '                    "stages": {\n'
    '                        "search_requests_completed": 1,\n'
    '                        "search_provider_fallbacks": int(search_provider_fallback_used),\n',
)

replace_once(
    "scripts/run_job_scout_live.py",
    '        ("search_requests_failed", "search_failed"),\n',
    '        ("search_requests_failed", "search_failed"),\n        ("search_provider_fallbacks", "search_fallbacks"),\n',
)
replace_once(
    "scripts/run_job_scout_live.py",
    '                "search_requests_failed",\n                "search_results_returned",\n',
    '                "search_requests_failed",\n                "search_provider_fallbacks",\n                "search_results_returned",\n',
)

(ROOT / "tests/test_public_search_fallback.py").write_text(
    '''from __future__ import annotations

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
''',
    encoding="utf-8",
)

print("public search fallback patch applied")
