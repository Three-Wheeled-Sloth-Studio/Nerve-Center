import asyncio
import json

import httpx

from nerve_center.discovery.connectors.greenhouse import GreenhouseConnector
from nerve_center.discovery.connectors.json_ld import JsonLdJobConnector
from nerve_center.discovery.connectors.lever import LeverConnector
from nerve_center.discovery.connectors.sitemap import SitemapConnector
from nerve_center.discovery.fetching import HttpFetcher
from nerve_center.discovery.models import (
    AcquisitionClass,
    Company,
    DiscoverySource,
    SourceKind,
    WorkArrangement,
)


def _company() -> Company:
    return Company(
        id="company-1",
        canonical_name="Example Co",
        domain="example.com",
    )


def _source(kind: SourceKind, **configuration: object) -> DiscoverySource:
    return DiscoverySource(
        id=f"source-{kind.value}",
        company_id="company-1",
        name=kind.value,
        kind=kind,
        acquisition_class=AcquisitionClass.OFFICIAL_API,
        base_url="https://example.com/careers",
        configuration=configuration,
        parser_version="test-v1",
    )


def test_greenhouse_normalizes_public_jobs() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/boards/example/jobs")
        assert request.url.params["content"] == "true"
        return httpx.Response(
            200,
            json={
                "jobs": [
                    {
                        "id": 42,
                        "title": "Director, Data Products",
                        "absolute_url": "https://boards.greenhouse.io/example/jobs/42?gh_src=test",
                        "updated_at": "2026-08-01T12:00:00Z",
                        "location": {"name": "Greensboro, NC (Hybrid)"},
                        "content": "<p>Lead analytics products.</p>",
                        "departments": [{"name": "Product"}],
                        "offices": [{"name": "Greensboro"}],
                    }
                ]
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = asyncio.run(
        GreenhouseConnector().scan(
            _company(),
            _source(SourceKind.GREENHOUSE, board_token="example"),
            HttpFetcher(client=client),
        )
    )
    asyncio.run(client.aclose())

    opening = result.openings[0]
    assert opening.external_id == "42"
    assert opening.canonical_url == "https://boards.greenhouse.io/example/jobs/42"
    assert opening.department == "Product"
    assert opening.work_arrangement is WorkArrangement.HYBRID
    assert opening.provenance[0].direct_employer_source is True


def test_lever_paginates_and_normalizes() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        skip = int(request.url.params["skip"])
        if skip == 0:
            payload = [
                {
                    "id": "lever-1",
                    "text": "Senior Product Manager",
                    "hostedUrl": "https://jobs.lever.co/example/lever-1",
                    "applyUrl": "https://jobs.lever.co/example/lever-1/apply",
                    "createdAt": 1785585600000,
                    "workplaceType": "remote",
                    "categories": {
                        "location": "North Carolina",
                        "allLocations": ["North Carolina"],
                        "commitment": "Full-time",
                        "team": "Product",
                    },
                    "descriptionPlain": "Build workflow products.",
                }
            ]
        else:
            payload = []
        return httpx.Response(200, json=payload)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = asyncio.run(
        LeverConnector().scan(
            _company(),
            _source(SourceKind.LEVER, site="example", page_size=1),
            HttpFetcher(client=client),
        )
    )
    asyncio.run(client.aclose())

    assert calls == 2
    assert result.requests_made == 2
    assert result.openings[0].work_arrangement is WorkArrangement.REMOTE
    assert result.openings[0].team == "Product"


def test_json_ld_extracts_nested_jobposting() -> None:
    job = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "JobPosting",
                "title": "Product Analytics Lead",
                "description": "<p>Lead product analytics.</p>",
                "datePosted": "2026-08-02",
                "validThrough": "2026-09-01T23:59:59Z",
                "employmentType": ["FULL_TIME"],
                "jobLocationType": "TELECOMMUTE",
                "applicantLocationRequirements": {"@type": "Country", "name": "US"},
                "hiringOrganization": {"@type": "Organization", "name": "Example Co"},
                "identifier": {"@type": "PropertyValue", "value": "PA-17"},
                "url": "https://example.com/careers/pa-17?utm_source=test",
            }
        ],
    }
    page = f'<html><script type="application/ld+json">{json.dumps(job)}</script></html>'

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=page, request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = asyncio.run(
        JsonLdJobConnector().scan(
            _company(),
            _source(SourceKind.JSON_LD),
            HttpFetcher(client=client),
        )
    )
    asyncio.run(client.aclose())

    opening = result.openings[0]
    assert opening.external_id == "PA-17"
    assert opening.canonical_url == "https://example.com/careers/pa-17"
    assert opening.work_arrangement is WorkArrangement.REMOTE
    assert opening.locations == ["US"]


def test_sitemap_returns_only_likely_job_urls() -> None:
    xml = """<?xml version='1.0'?>
    <urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>
      <url><loc>https://example.com/about</loc></url>
      <url><loc>https://example.com/careers/product-manager</loc></url>
      <url><loc>https://example.com/jobs/data-lead</loc></url>
    </urlset>"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=xml, request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = asyncio.run(
        SitemapConnector().scan(
            _company(),
            _source(SourceKind.SITEMAP),
            HttpFetcher(client=client),
        )
    )
    asyncio.run(client.aclose())

    assert len(result.discovered_urls) == 2
    assert all("about" not in item for item in result.discovered_urls)
