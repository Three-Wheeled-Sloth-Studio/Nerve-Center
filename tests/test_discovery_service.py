import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from nerve_center.config import Settings
from nerve_center.discovery.fetching import FetchResponse, HttpFetcher
from nerve_center.discovery.models import (
    AcquisitionClass,
    Company,
    DiscoverySource,
    SourceKind,
)
from nerve_center.discovery.plugin import JobDiscoveryTaskPlugin
from nerve_center.discovery.search import (
    PlaywrightSearchAdapter,
    PublicWebSearchAdapter,
    SearchChallengeError,
    UrlClassification,
    classify_discovered_url,
    normalize_google_result_url,
    normalize_public_search_result_url,
)
from nerve_center.discovery.service import DiscoveryService
from nerve_center.domain.budget import ResourceBudget, ResourceBudgetTracker
from nerve_center.domain.task import TaskContext, TaskStatus
from nerve_center.persistence.database import Database
from nerve_center.persistence.discovery import (
    CompanyRepository,
    DiscoverySourceRepository,
    JobOpeningRepository,
    SearchCacheRepository,
)


def _setup(tmp_path: Path, handler):  # type: ignore[no-untyped-def]
    database = Database(Settings(data_dir=tmp_path / "runtime"))
    database.initialize()
    companies = CompanyRepository(database)
    sources = DiscoverySourceRepository(database)
    jobs = JobOpeningRepository(database)
    company = Company(
        id="company-1",
        canonical_name="Example Co",
        domain="example.com",
    )
    source = DiscoverySource(
        id="source-1",
        company_id=company.id,
        name="Example Greenhouse",
        kind=SourceKind.GREENHOUSE,
        acquisition_class=AcquisitionClass.OFFICIAL_API,
        base_url="https://boards.greenhouse.io/example",
        configuration={"board_token": "example"},
        parser_version="greenhouse-v1",
        scan_interval_minutes=60,
    )
    companies.upsert(company)
    sources.upsert(source)
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    service = DiscoveryService(
        companies,
        sources,
        jobs,
        fetcher_factory=lambda before_request=None: HttpFetcher(
            client=client,
            before_request=before_request,
        ),
    )
    return service, sources, jobs, client


def test_service_scans_source_and_persists_job(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "jobs": [
                    {
                        "id": 7,
                        "title": "Product Manager",
                        "absolute_url": "https://example.com/jobs/7",
                        "location": {"name": "Greensboro, NC"},
                        "content": "<p>Build products.</p>",
                    }
                ]
            },
        )

    service, sources, jobs, client = _setup(tmp_path, handler)
    result = asyncio.run(service.scan_source("source-1"))
    asyncio.run(client.aclose())

    assert len(result.openings) == 1
    assert jobs.list()[0].title == "Product Manager"
    assert sources.get("source-1").last_success_at is not None


def test_plugin_checkpoints_and_consumes_request_budget(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"jobs": []})

    service, sources, _jobs, client = _setup(tmp_path, handler)
    checkpoints: list[dict[str, object]] = []
    context = TaskContext(
        run_id="run-1",
        started_at=datetime.now(UTC),
        deadline=datetime.now(UTC) + timedelta(minutes=5),
        cancellation_requested=lambda: False,
        save_checkpoint=lambda item: checkpoints.append(dict(item)),
        resources=ResourceBudgetTracker(
            ResourceBudget(max_requests=5, max_llm_calls=1, max_parallel_work=1)
        ),
        configuration={"source_ids": ["source-1"]},
    )

    result = asyncio.run(JobDiscoveryTaskPlugin(service, sources).run(context))
    asyncio.run(client.aclose())

    assert result.status is TaskStatus.SUCCEEDED
    assert context.resources.usage.requests == 1
    assert checkpoints[0]["completed_source_ids"] == ["source-1"]


def test_google_result_normalization_rejects_internal_links() -> None:
    assert (
        normalize_google_result_url(
            "https://www.google.com/url?q=https%3A%2F%2Fexample.com%2Fjobs%2F1%3Futm_source%3Dx"
        )
        == "https://example.com/jobs/1"
    )
    assert normalize_google_result_url("https://www.google.com/preferences") is None
    assert classify_discovered_url("https://acme.com/careers/product") is (
        UrlClassification.COMPANY_CAREER
    )
    assert classify_discovered_url("https://www.linkedin.com/jobs/view/1") is (
        UrlClassification.LINKEDIN
    )
    assert classify_discovered_url("https://builtin.com/job/product-manager") is (
        UrlClassification.MAJOR_JOB_BOARD
    )
    assert classify_discovered_url("https://wellfound.com/jobs/123") is (
        UrlClassification.MAJOR_JOB_BOARD
    )


def test_public_search_discovers_supported_result_pages(tmp_path: Path) -> None:
    database = Database(Settings(data_dir=tmp_path / "runtime"))
    database.initialize()
    cache = SearchCacheRepository(database)

    class FakeFetcher:
        async def get(self, url: str, **kwargs: object) -> FetchResponse:
            assert url == "https://builtin.com/jobs"
            assert kwargs["params"] == {"search": "product director"}
            return FetchResponse(
                url=url,
                status_code=200,
                text="""
                    <a href="/job/director-product/8120141">
                      <div>Director of Product</div>
                    </a>
                    <a href="https://builtin.com/jobs/categories/product">Product jobs</a>
                    <a href="https://acme.example/careers/product-director">Acme role</a>
                """,
                headers={},
                challenged=False,
                throttled=False,
            )

    adapter = PublicWebSearchAdapter(cache, fetcher=FakeFetcher(), max_results=10)  # type: ignore[arg-type]
    results = asyncio.run(adapter.search("site:builtin.com product director"))

    assert [item.url for item in results] == ["https://builtin.com/job/director-product/8120141"]
    assert results[0].classification is UrlClassification.MAJOR_JOB_BOARD
    assert normalize_public_search_result_url("https://search.brave.com/help") is None
    assert (
        normalize_public_search_result_url(
            "//duckduckgo.com/l/?uddg=https%3A%2F%2Fbuiltin.com%2Fjob%2F123"
        )
        == "https://builtin.com/job/123"
    )


def test_cached_browser_challenge_prevents_repeated_headless_attempts(
    tmp_path: Path,
) -> None:
    database = Database(Settings(data_dir=tmp_path / "runtime"))
    database.initialize()
    cache = SearchCacheRepository(database)
    cache.put(
        "playwright_google:25",
        "product manager",
        {"status": "challenged", "message": "Cooling down."},
        ttl=timedelta(hours=1),
    )
    adapter = PlaywrightSearchAdapter(cache, tmp_path / "browser", headless=True)

    with pytest.raises(SearchChallengeError, match="Cooling down"):
        asyncio.run(adapter.search("product manager"))
