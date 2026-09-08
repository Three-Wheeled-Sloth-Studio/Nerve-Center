"""Optional cached Playwright broad-search proof of concept."""

from __future__ import annotations

import re
from datetime import timedelta
from enum import StrEnum
from html.parser import HTMLParser
from pathlib import Path
from typing import Protocol
from urllib.parse import parse_qs, quote_plus, urlsplit

import httpx
from pydantic import BaseModel, ConfigDict

from nerve_center.discovery.fetching import DomainRequestGate, HttpFetcher
from nerve_center.discovery.normalization import canonicalize_url
from nerve_center.persistence.discovery import SearchCacheRepository


class SearchChallengeError(RuntimeError):
    pass


class UrlClassification(StrEnum):
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    ASHBY = "ashby"
    LINKEDIN = "linkedin"
    MAJOR_JOB_BOARD = "major_job_board"
    COMPANY_CAREER = "company_career"
    OTHER = "other"


class SearchResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    title: str
    url: str
    snippet: str = ""
    classification: UrlClassification = UrlClassification.OTHER
    domain: str = ""


class SearchAdapter(Protocol):
    async def search(self, query: str) -> list[SearchResult]: ...


class _PublicSearchResultParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.anchors: list[tuple[str, str]] = []
        self._href: str | None = None
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._href is not None:
            return
        if tag != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self._href = href
            self._parts = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._href is None or tag != "a":
            return
        self.anchors.append((self._href, " ".join("".join(self._parts).split())))
        self._href = None
        self._parts = []


class PublicWebSearchAdapter:
    """Cached ordinary public-web search without browser automation."""

    provider = "duckduckgo_html"

    def __init__(
        self,
        cache: SearchCacheRepository,
        *,
        fetcher: HttpFetcher | None = None,
        max_results: int = 25,
    ) -> None:
        self.cache = cache
        self.fetcher = fetcher or HttpFetcher(
            gate=DomainRequestGate(1, minimum_interval_seconds=3.0)
        )
        self.max_results = max_results
        self._cooldown_messages: dict[str, str] = {}

    async def search(self, query: str) -> list[SearchResult]:
        builtin_query = _board_native_query(query, "builtin.com")
        provider = "builtin_html" if builtin_query is not None else self.provider
        if provider in self._cooldown_messages:
            raise SearchChallengeError(self._cooldown_messages[provider])
        cache_provider = f"{provider}:{self.max_results}"
        cached = self.cache.get(cache_provider, query)
        if cached is not None:
            if cached.get("status") == "challenged":
                raise SearchChallengeError(
                    str(cached.get("message") or "Public search is cooling down after a challenge.")
                )
            if cached.get("status") == "succeeded":
                return [SearchResult.model_validate(item) for item in cached.get("results", [])]

        search_url = (
            "https://builtin.com/jobs"
            if builtin_query is not None
            else "https://html.duckduckgo.com/html/"
        )
        params = (
            _builtin_search_params(builtin_query)
            if builtin_query is not None
            else {"q": query, "source": "web"}
        )
        try:
            response = await self.fetcher.get(
                search_url,
                params=params,
                headers={"Accept": "text/html,application/xhtml+xml"},
            )
        except httpx.RequestError as error:
            raise RuntimeError("The public search provider could not be reached.") from error
        if response.challenged or response.throttled or response.status_code in {401, 403, 429}:
            message = "The public search provider requested a cooldown; try the scan again later."
            self._cooldown_messages[provider] = message
            self.cache.put(
                cache_provider,
                query,
                {"status": "challenged", "message": message},
                ttl=timedelta(hours=1),
            )
            raise SearchChallengeError(message)
        if response.status_code >= 400:
            raise RuntimeError(f"Public search failed with HTTP {response.status_code}.")

        parser = _PublicSearchResultParser()
        parser.feed(response.text)
        parser.close()
        results: list[SearchResult] = []
        seen: set[str] = set()
        for href, title in parser.anchors:
            if builtin_query is not None and href.startswith("/"):
                href = f"https://builtin.com{href}"
            url = normalize_public_search_result_url(href)
            if not url or not title or url in seen:
                continue
            if builtin_query is not None:
                split = urlsplit(url)
                if (split.hostname or "").casefold().removeprefix("www.") != "builtin.com":
                    continue
                if not split.path.casefold().startswith("/job/"):
                    continue
            classification = classify_discovered_url(url)
            if classification is UrlClassification.OTHER:
                continue
            seen.add(url)
            results.append(
                SearchResult(
                    title=title[:300],
                    url=url,
                    classification=classification,
                    domain=(urlsplit(url).hostname or "").removeprefix("www."),
                )
            )
            if len(results) >= self.max_results:
                break
        self.cache.put(
            cache_provider,
            query,
            {
                "status": "succeeded",
                "results": [item.model_dump(mode="json") for item in results],
            },
            ttl=timedelta(days=1),
        )
        return results


def _board_native_query(query: str, domain: str) -> str | None:
    prefix = f"site:{domain} "
    if not query.casefold().startswith(prefix):
        return None
    return query[len(prefix) :].strip() or None


def _builtin_search_params(query: str) -> dict[str, str]:
    match = re.fullmatch(r'"([^"]+)"\s*(.*?)\s+jobs careers', query, re.IGNORECASE)
    if match is None:
        return {"search": query}
    params = {"search": match.group(1).strip()}
    location = match.group(2).strip()
    if location:
        params["location"] = location
    return params


class PlaywrightSearchAdapter:
    provider = "playwright_google"

    def __init__(
        self,
        cache: SearchCacheRepository,
        profile_dir: Path,
        *,
        headless: bool = True,
        max_results: int = 25,
        manual_challenge_timeout_seconds: int = 300,
    ) -> None:
        self.cache = cache
        self.profile_dir = profile_dir
        self.headless = headless
        self.max_results = max_results
        self.manual_challenge_timeout_seconds = manual_challenge_timeout_seconds

    async def search(self, query: str) -> list[SearchResult]:
        cache_provider = f"{self.provider}:{self.max_results}"
        cached = self.cache.get(cache_provider, query)
        if cached is not None:
            if cached.get("status") == "challenged" and self.headless:
                raise SearchChallengeError(
                    str(cached.get("message") or "Search is cooling down after a challenge.")
                )
            if cached.get("status") == "succeeded":
                return [SearchResult.model_validate(item) for item in cached.get("results", [])]
        try:
            from playwright.async_api import async_playwright
        except ImportError as error:
            raise RuntimeError(
                "Playwright search requires the optional search dependencies."
            ) from error

        self.profile_dir.mkdir(parents=True, exist_ok=True)
        async with async_playwright() as playwright:
            context = await playwright.chromium.launch_persistent_context(
                user_data_dir=str(self.profile_dir),
                headless=self.headless,
                viewport={"width": 1440, "height": 1000},
            )
            try:
                page = context.pages[0] if context.pages else await context.new_page()
                await page.goto(
                    f"https://www.google.com/search?q={quote_plus(query)}",
                    wait_until="domcontentloaded",
                    timeout=45_000,
                )
                challenge_markers = (
                    "unusual traffic",
                    "verify you are human",
                    "our systems have detected",
                    "captcha",
                )
                body_text = (await page.locator("body").inner_text()).casefold()
                challenged = any(marker in body_text for marker in challenge_markers)
                if challenged and not self.headless:
                    attempts = max(self.manual_challenge_timeout_seconds // 2, 1)
                    for _ in range(attempts):
                        await page.wait_for_timeout(2000)
                        body_text = (await page.locator("body").inner_text()).casefold()
                        challenged = any(marker in body_text for marker in challenge_markers)
                        if not challenged:
                            break
                if challenged:
                    message = (
                        "Google presented a challenge page. "
                        "Headful manual continuation is required after the cooldown."
                    )
                    self.cache.put(
                        cache_provider,
                        query,
                        {"status": "challenged", "message": message},
                        ttl=timedelta(hours=1),
                    )
                    raise SearchChallengeError(message)
                anchors = await page.locator("a[href]").evaluate_all(
                    "els => els.map(a => ({href: a.href, text: a.innerText || ''}))"
                )
            finally:
                await context.close()
        results: list[SearchResult] = []
        seen: set[str] = set()
        for anchor in anchors:
            if not isinstance(anchor, dict):
                continue
            url = normalize_google_result_url(str(anchor.get("href") or ""))
            title = " ".join(str(anchor.get("text") or "").split())
            if not url or not title or url in seen:
                continue
            seen.add(url)
            classification = classify_discovered_url(url)
            results.append(
                SearchResult(
                    title=title,
                    url=url,
                    classification=classification,
                    domain=(urlsplit(url).hostname or "").removeprefix("www."),
                )
            )
            if len(results) >= self.max_results:
                break
        self.cache.put(
            cache_provider,
            query,
            {
                "status": "succeeded",
                "results": [item.model_dump(mode="json") for item in results],
            },
            ttl=timedelta(days=7),
        )
        return results


def normalize_google_result_url(value: str) -> str | None:
    if not value:
        return None
    split = urlsplit(value)
    hostname = (split.hostname or "").casefold()
    if hostname.endswith("google.com") and split.path == "/url":
        values = parse_qs(split.query).get("q") or parse_qs(split.query).get("url")
        value = values[0] if values else ""
        split = urlsplit(value)
        hostname = (split.hostname or "").casefold()
    if split.scheme not in {"http", "https"}:
        return None
    if hostname.endswith("google.com") or hostname.endswith("googleusercontent.com"):
        return None
    return canonicalize_url(value)


def normalize_public_search_result_url(value: str) -> str | None:
    if not value:
        return None
    if value.startswith("//"):
        value = f"https:{value}"
    split = urlsplit(value)
    hostname = (split.hostname or "").casefold().removeprefix("www.")
    if hostname == "duckduckgo.com" and split.path == "/l/":
        values = parse_qs(split.query).get("uddg")
        value = values[0] if values else ""
        split = urlsplit(value)
        hostname = (split.hostname or "").casefold().removeprefix("www.")
    if split.scheme not in {"http", "https"}:
        return None
    if hostname in {"search.brave.com", "brave.com", "duckduckgo.com"}:
        return None
    return canonicalize_url(value)


def classify_discovered_url(value: str) -> UrlClassification:
    split = urlsplit(value)
    domain = (split.hostname or "").casefold().removeprefix("www.")
    path = split.path.casefold()
    if domain.endswith("greenhouse.io"):
        return UrlClassification.GREENHOUSE
    if domain.endswith("lever.co"):
        return UrlClassification.LEVER
    if domain.endswith("ashbyhq.com"):
        return UrlClassification.ASHBY
    if domain.endswith("linkedin.com"):
        return UrlClassification.LINKEDIN
    if any(
        domain.endswith(item)
        for item in (
            "indeed.com",
            "glassdoor.com",
            "ziprecruiter.com",
            "monster.com",
            "careerbuilder.com",
            "builtin.com",
            "wellfound.com",
        )
    ):
        return UrlClassification.MAJOR_JOB_BOARD
    if any(token in path for token in ("/career", "/careers", "/job", "/jobs")):
        return UrlClassification.COMPANY_CAREER
    return UrlClassification.OTHER
