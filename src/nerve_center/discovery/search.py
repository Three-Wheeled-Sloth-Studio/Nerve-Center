"""Optional cached Playwright broad-search proof of concept."""

from __future__ import annotations

from datetime import timedelta
from enum import StrEnum
from pathlib import Path
from typing import Protocol
from urllib.parse import parse_qs, quote_plus, urlsplit

from pydantic import BaseModel, ConfigDict

from nerve_center.discovery.normalization import canonicalize_url
from nerve_center.persistence.discovery import SearchCacheRepository


class SearchChallengeError(RuntimeError):
    pass


class UrlClassification(StrEnum):
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
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


def classify_discovered_url(value: str) -> UrlClassification:
    split = urlsplit(value)
    domain = (split.hostname or "").casefold().removeprefix("www.")
    path = split.path.casefold()
    if domain.endswith("greenhouse.io"):
        return UrlClassification.GREENHOUSE
    if domain.endswith("lever.co"):
        return UrlClassification.LEVER
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
        )
    ):
        return UrlClassification.MAJOR_JOB_BOARD
    if any(token in path for token in ("/career", "/careers", "/job", "/jobs")):
        return UrlClassification.COMPANY_CAREER
    return UrlClassification.OTHER
