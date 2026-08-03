"""Local API routes for company, source, scan, job, and search inspection."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from nerve_center.config import Settings
from nerve_center.discovery.models import (
    AcquisitionClass,
    Company,
    ConnectorScanResult,
    DiscoverySource,
    NormalizedJobOpening,
    SourceKind,
    SourceScanRecord,
)
from nerve_center.discovery.normalization import (
    canonical_domain,
    canonicalize_url,
    stable_company_id,
    stable_source_id,
)
from nerve_center.discovery.search import (
    PlaywrightSearchAdapter,
    SearchChallengeError,
    SearchResult,
    UrlClassification,
)
from nerve_center.discovery.service import DiscoveryService
from nerve_center.persistence.database import Database
from nerve_center.persistence.discovery import (
    CompanyRepository,
    DiscoverySourceRepository,
    JobOpeningRepository,
    SearchCacheRepository,
)


class CompanyCreateRequest(BaseModel):
    canonical_name: str = Field(min_length=1, max_length=255)
    domain: str = Field(min_length=1, max_length=255)
    career_url: str | None = Field(default=None, max_length=4096)
    ats_type: str | None = Field(default=None, max_length=50)


class SourceCreateRequest(BaseModel):
    company_id: str
    name: str = Field(min_length=1, max_length=255)
    kind: SourceKind
    acquisition_class: AcquisitionClass
    base_url: str = Field(min_length=1, max_length=4096)
    configuration: dict[str, Any] = Field(default_factory=dict)
    parser_version: str | None = Field(default=None, max_length=100)
    scan_interval_minutes: int = Field(default=1440, ge=5)
    policy_notes: str | None = Field(default=None, max_length=2000)


class BrowserSearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    headless: bool = True
    max_results: int = Field(default=25, ge=1, le=100)


def register_discovery_routes(
    application: FastAPI,
    database: Database,
    settings: Settings,
    service: DiscoveryService | None = None,
) -> DiscoveryService:
    companies = CompanyRepository(database)
    sources = DiscoverySourceRepository(database)
    jobs = JobOpeningRepository(database)
    runtime_service = service or DiscoveryService(companies, sources, jobs)
    search_cache = SearchCacheRepository(database)

    application.state.discovery_service = runtime_service
    application.state.company_repository = companies
    application.state.discovery_source_repository = sources
    application.state.job_repository = jobs

    @application.post(
        "/api/v1/discovery/companies",
        status_code=status.HTTP_201_CREATED,
    )
    def create_company(request: CompanyCreateRequest) -> Company:
        now = datetime.now(UTC)
        domain = canonical_domain(request.domain)
        if not domain:
            raise HTTPException(status_code=422, detail="A valid company domain is required.")
        return companies.upsert(
            Company(
                id=stable_company_id(domain),
                canonical_name=request.canonical_name.strip(),
                domain=domain,
                career_url=(
                    canonicalize_url(request.career_url) if request.career_url else None
                ),
                ats_type=request.ats_type,
                created_at=now,
                updated_at=now,
            )
        )

    @application.get("/api/v1/discovery/companies")
    def list_companies() -> list[Company]:
        return companies.list()

    @application.post(
        "/api/v1/discovery/sources",
        status_code=status.HTTP_201_CREATED,
    )
    def create_source(request: SourceCreateRequest) -> DiscoverySource:
        try:
            companies.get(request.company_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        base_url = canonicalize_url(request.base_url)
        return sources.upsert(
            DiscoverySource(
                id=stable_source_id(request.kind.value, base_url),
                company_id=request.company_id,
                name=request.name.strip(),
                kind=request.kind,
                acquisition_class=request.acquisition_class,
                base_url=base_url,
                configuration=request.configuration,
                parser_version=request.parser_version or f"{request.kind.value}-v1",
                scan_interval_minutes=request.scan_interval_minutes,
                policy_notes=request.policy_notes,
            )
        )

    @application.get("/api/v1/discovery/sources")
    def list_sources() -> list[DiscoverySource]:
        return sources.list()

    @application.get("/api/v1/discovery/sources/{source_id}/scans")
    def list_source_scans(source_id: str) -> list[SourceScanRecord]:
        try:
            return sources.list_scans(source_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @application.post("/api/v1/discovery/sources/{source_id}/scan")
    async def scan_source(source_id: str) -> ConnectorScanResult:
        try:
            return await runtime_service.scan_source(source_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @application.get("/api/v1/discovery/jobs")
    def list_jobs() -> list[NormalizedJobOpening]:
        return jobs.list()

    @application.post("/api/v1/discovery/search")
    async def browser_search(request: BrowserSearchRequest) -> list[SearchResult]:
        adapter = PlaywrightSearchAdapter(
            search_cache,
            Path(settings.data_dir) / "browser-profiles" / "search",
            headless=request.headless,
            max_results=request.max_results,
        )
        try:
            results = await adapter.search(request.query)
            for result in results:
                if result.classification is UrlClassification.COMPANY_CAREER:
                    runtime_service.register_direct_career_url(result.url, result.title)
            return results
        except SearchChallengeError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error

    return runtime_service
