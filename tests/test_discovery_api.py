import asyncio
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from nerve_center.config import Settings
from nerve_center.discovery.api import register_discovery_routes
from nerve_center.discovery.fetching import HttpFetcher
from nerve_center.discovery.service import DiscoveryService
from nerve_center.persistence.database import Database
from nerve_center.persistence.discovery import (
    CompanyRepository,
    DiscoverySourceRepository,
    JobOpeningRepository,
)


def test_discovery_api_registers_scans_and_lists_jobs(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path / "runtime")
    database = Database(settings)
    database.initialize()
    companies = CompanyRepository(database)
    sources = DiscoverySourceRepository(database)
    jobs = JobOpeningRepository(database)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "jobs": [
                    {
                        "id": 9,
                        "title": "Data Product Lead",
                        "absolute_url": "https://example.com/jobs/9",
                        "location": {"name": "Greensboro, NC"},
                        "content": "<p>Lead data products.</p>",
                    }
                ]
            },
        )

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
    application = FastAPI()
    register_discovery_routes(application, database, settings, service)

    with TestClient(application) as api:
        company = api.post(
            "/api/v1/discovery/companies",
            json={"canonical_name": "Example Co", "domain": "example.com"},
        ).json()
        source = api.post(
            "/api/v1/discovery/sources",
            json={
                "company_id": company["id"],
                "name": "Example Greenhouse",
                "kind": "greenhouse",
                "acquisition_class": "official_api",
                "base_url": "https://boards.greenhouse.io/example",
                "configuration": {"board_token": "example"},
                "parser_version": "greenhouse-v1",
            },
        ).json()
        scan = api.post(f"/api/v1/discovery/sources/{source['id']}/scan").json()
        scans = api.get(f"/api/v1/discovery/sources/{source['id']}/scans").json()
        openings = api.get("/api/v1/discovery/jobs").json()

    asyncio.run(client.aclose())
    assert scan["status"] == "succeeded"
    assert scans[0]["openings_found"] == 1
    assert scans[0]["requests_made"] == 1
    assert openings[0]["title"] == "Data Product Lead"
