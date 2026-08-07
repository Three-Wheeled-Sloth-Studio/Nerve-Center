"""Module-owned Job Scout setup and basic scanning API."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from nerve_center.config import Settings
from nerve_center.discovery.connectors.greenhouse import GreenhouseConnector
from nerve_center.discovery.connectors.lever import LeverConnector
from nerve_center.discovery.models import (
    AcquisitionClass,
    Company,
    DiscoverySource,
    ScanStatus,
    SourceKind,
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
from nerve_center.persistence.profile import CareerProfileRepository, SourceDocumentRepository
from nerve_center.plugins.job_scout.settings import (
    JobScoutConfiguration,
    JobScoutConfigurationStore,
    JobScoutKeywordSummary,
    JobScoutSuggestionSummary,
    ResumeLoadRequest,
    clean_list,
    discover_keywords,
    discover_suggestions,
)
from nerve_center.profile.documents import DocumentImportError, import_source_document
from nerve_center.profile.models import CanonicalCareerProfile, SourceDocument
from nerve_center.profile.service import CareerProfileService
from nerve_center.providers.base import StructuredProvider
from nerve_center.providers.errors import ProviderError


class JobScoutSourceScan(BaseModel):
    source_id: str
    source_name: str
    status: str
    openings_found: int
    requests_made: int
    detail: dict[str, Any] = Field(default_factory=dict)


class JobScoutScanRequest(BaseModel):
    discover_sources: bool | None = None
    headless: bool = True
    max_queries: int = Field(default=5, ge=0, le=20)
    max_results_per_query: int = Field(default=20, ge=1, le=50)


class JobScoutScanSummary(BaseModel):
    queries_run: list[str]
    search_results_seen: int
    sources_registered: int
    sources_scanned: int
    openings_found: int
    scans: list[JobScoutSourceScan]
    warnings: list[str]


class JobScoutWorkspace(BaseModel):
    configuration: JobScoutConfiguration
    documents: list[SourceDocument]
    profile: CanonicalCareerProfile
    keywords: JobScoutKeywordSummary
    suggestions: JobScoutSuggestionSummary
    sources: list[DiscoverySource]
    opening_count: int


class JobScoutCoordinator:
    def __init__(
        self,
        settings: Settings,
        database: Database,
        provider: StructuredProvider | None,
        discovery: DiscoveryService,
        companies: CompanyRepository,
        sources: DiscoverySourceRepository,
        jobs: JobOpeningRepository,
    ) -> None:
        self.settings = settings
        self.provider = provider
        self.discovery = discovery
        self.companies = companies
        self.sources = sources
        self.jobs = jobs
        self.documents = SourceDocumentRepository(database)
        self.profiles = CareerProfileRepository(database)
        self.store = JobScoutConfigurationStore(settings)
        self.search_cache = SearchCacheRepository(database)

    def workspace(self) -> JobScoutWorkspace:
        configuration = self.store.load()
        document = self._resume_document(configuration)
        return JobScoutWorkspace(
            configuration=configuration,
            documents=self.documents.list(),
            profile=self.profiles.get_profile(),
            keywords=self._discover_keywords(configuration, document=document),
            suggestions=discover_suggestions(
                configuration, self.profiles.get_profile(), document
            ),
            sources=self._configured_sources(configuration),
            opening_count=len(self.jobs.list()),
        )

    def save_configuration(
        self,
        configuration: JobScoutConfiguration,
    ) -> JobScoutConfiguration:
        registered_ids: list[str] = []
        for source_url in configuration.source_urls:
            self._validate_source_policy(source_url, configuration)
            registered_ids.append(
                self._register_source_url(source_url, configuration.scan_interval_minutes).id
            )
        merged = configuration.model_copy(
            update={"source_ids": clean_list([*configuration.source_ids, *registered_ids])}
        )
        return self.store.save(merged)

    async def load_resume(self, request: ResumeLoadRequest) -> JobScoutWorkspace:
        document = import_source_document(Path(request.path))
        self.documents.save(document)
        if request.analyze_resume:
            if self.provider is None:
                raise ProviderError(
                    provider="manager",
                    code="PROVIDER_UNAVAILABLE",
                    safe_message="No manager-owned model provider is available.",
                    retryable=True,
                )
            await CareerProfileService(self.profiles, self.provider).extract_document(document)
        configuration = self.store.load().model_copy(
            update={
                "resume_document_id": document.id,
                "resume_file_name": document.file_name,
            }
        )
        summary = self._discover_keywords(configuration, document=document)
        configuration = configuration.model_copy(
            update={"keywords": clean_list([*configuration.keywords, *summary.keywords])}
        )
        self.store.save(configuration)
        return self.workspace()

    def refresh_keywords(self) -> JobScoutWorkspace:
        configuration = self.store.load()
        summary = self._discover_keywords(configuration)
        self.store.save(
            configuration.model_copy(
                update={"keywords": clean_list([*configuration.keywords, *summary.keywords])}
            )
        )
        return self.workspace()

    async def scan(self, request: JobScoutScanRequest) -> JobScoutScanSummary:
        configuration = self.save_configuration(self.store.load())
        keyword_summary = self._discover_keywords(configuration)
        discover_sources = (
            configuration.broad_search_enabled
            if request.discover_sources is None
            else request.discover_sources
        )
        queries = keyword_summary.search_queries[: request.max_queries] if discover_sources else []
        warnings: list[str] = []
        results_seen = 0
        registered_before = set(configuration.source_ids)
        registered_ids = list(configuration.source_ids)

        if queries:
            adapter = PlaywrightSearchAdapter(
                self.search_cache,
                Path(self.settings.data_dir) / "browser-profiles" / "job-scout",
                headless=request.headless,
                max_results=request.max_results_per_query,
            )
            for query in queries:
                try:
                    results = await adapter.search(query)
                except SearchChallengeError as error:
                    warnings.append(str(error))
                    break
                except RuntimeError as error:
                    warnings.append(str(error))
                    break
                results_seen += len(results)
                for result in results:
                    if result.classification not in {
                        UrlClassification.GREENHOUSE,
                        UrlClassification.LEVER,
                        UrlClassification.MAJOR_JOB_BOARD,
                        UrlClassification.COMPANY_CAREER,
                    }:
                        continue
                    try:
                        self._validate_source_policy(result.url, configuration)
                        registered_ids.append(
                            self._register_source_url(
                                result.url,
                                configuration.scan_interval_minutes,
                            ).id
                        )
                    except ValueError as error:
                        warnings.append(str(error))

        configuration = self.store.save(
            configuration.model_copy(update={"source_ids": clean_list(registered_ids)})
        )
        scans: list[JobScoutSourceScan] = []
        openings_found = 0
        for source in self._configured_sources(configuration):
            try:
                result = await self.discovery.scan_source(source.id)
                openings_found += len(result.openings)
                scans.append(
                    JobScoutSourceScan(
                        source_id=source.id,
                        source_name=source.name,
                        status=result.status.value,
                        openings_found=len(result.openings),
                        requests_made=result.requests_made,
                        detail=result.safe_detail,
                    )
                )
            except (KeyError, ValueError) as error:
                scans.append(
                    JobScoutSourceScan(
                        source_id=source.id,
                        source_name=source.name,
                        status=ScanStatus.FAILED.value,
                        openings_found=0,
                        requests_made=0,
                        detail={"message": str(error)},
                    )
                )

        return JobScoutScanSummary(
            queries_run=queries,
            search_results_seen=results_seen,
            sources_registered=len(set(configuration.source_ids) - registered_before),
            sources_scanned=len(scans),
            openings_found=openings_found,
            scans=scans,
            warnings=clean_list(warnings),
        )

    def _discover_keywords(
        self,
        configuration: JobScoutConfiguration,
        *,
        document: SourceDocument | None = None,
    ) -> JobScoutKeywordSummary:
        if document is None:
            document = self._resume_document(configuration)
        return discover_keywords(
            configuration,
            self.profiles.get_profile(),
            document,
        )

    def _resume_document(
        self, configuration: JobScoutConfiguration
    ) -> SourceDocument | None:
        if not configuration.resume_document_id:
            return None
        try:
            return self.documents.get(configuration.resume_document_id)
        except KeyError:
            return None

    def _configured_sources(
        self,
        configuration: JobScoutConfiguration,
    ) -> list[DiscoverySource]:
        result: list[DiscoverySource] = []
        for source_id in configuration.source_ids:
            try:
                result.append(self.sources.get(source_id))
            except KeyError:
                continue
        return result

    def _validate_source_policy(
        self,
        source_url: str,
        configuration: JobScoutConfiguration,
    ) -> None:
        domain = canonical_domain(source_url)
        if not domain:
            raise ValueError(f"Invalid source URL: {source_url}")
        disallowed = tuple(
            item.casefold().removeprefix("www.")
            for item in configuration.disallowed_domains
        )
        if any(domain == item or domain.endswith(f".{item}") for item in disallowed):
            raise ValueError(f"Source domain is disallowed: {domain}")
        allowed = tuple(
            item.casefold().removeprefix("www.")
            for item in configuration.allowed_domains
        )
        if allowed and not any(domain == item or domain.endswith(f".{item}") for item in allowed):
            raise ValueError(f"Source domain is outside the allow list: {domain}")

    def _register_source_url(self, source_url: str, interval: int) -> DiscoverySource:
        canonical = canonicalize_url(source_url)
        split = urlsplit(canonical)
        domain = (split.hostname or "").casefold().removeprefix("www.")
        segments = [item for item in split.path.split("/") if item]
        if domain.endswith("greenhouse.io"):
            token = _greenhouse_token(segments)
            if token:
                return self._register_ats_source(
                    token,
                    f"https://boards.greenhouse.io/{token}",
                    SourceKind.GREENHOUSE,
                    AcquisitionClass.OFFICIAL_API,
                    {"board_token": token},
                    GreenhouseConnector.parser_version,
                    interval,
                )
        if domain.endswith("lever.co") and segments:
            site = segments[-1] if domain.startswith("api.") else segments[0]
            return self._register_ats_source(
                site,
                f"https://jobs.lever.co/{site}",
                SourceKind.LEVER,
                AcquisitionClass.OFFICIAL_API,
                {"site": site},
                LeverConnector.parser_version,
                interval,
            )
        source = self.discovery.register_direct_career_url(canonical)
        if source.scan_interval_minutes != interval:
            source = self.sources.upsert(
                source.model_copy(update={"scan_interval_minutes": interval})
            )
        return source

    def _register_ats_source(
        self,
        key: str,
        url: str,
        kind: SourceKind,
        acquisition: AcquisitionClass,
        source_configuration: dict[str, Any],
        parser_version: str,
        interval: int,
    ) -> DiscoverySource:
        synthetic_domain = f"{key.casefold()}.{kind.value}.jobs"
        company = self.companies.upsert(
            Company(
                id=stable_company_id(synthetic_domain),
                canonical_name=_display_name(key),
                domain=synthetic_domain,
                career_url=url,
                ats_type=kind.value,
            )
        )
        return self.sources.upsert(
            DiscoverySource(
                id=stable_source_id(kind.value, url),
                company_id=company.id,
                name=f"{company.canonical_name} via {kind.value.title()}",
                kind=kind,
                acquisition_class=acquisition,
                base_url=url,
                configuration=source_configuration,
                parser_version=parser_version,
                scan_interval_minutes=interval,
                policy_notes="Configured in the Job Scout module.",
            )
        )


def _greenhouse_token(segments: list[str]) -> str | None:
    if not segments:
        return None
    if "boards" in segments:
        index = segments.index("boards")
        if index + 1 < len(segments):
            return segments[index + 1]
    if segments[0] not in {"v1", "boards"}:
        return segments[0]
    return None


def _display_name(value: str) -> str:
    return re.sub(r"[-_]+", " ", value).strip().title() or value


def register_job_scout_configuration_routes(
    application: FastAPI,
    database: Database,
    settings: Settings,
    provider: StructuredProvider | None,
    discovery: DiscoveryService,
    companies: CompanyRepository,
    sources: DiscoverySourceRepository,
    jobs: JobOpeningRepository,
) -> JobScoutCoordinator:
    coordinator = JobScoutCoordinator(
        settings,
        database,
        provider,
        discovery,
        companies,
        sources,
        jobs,
    )
    application.state.job_scout_coordinator = coordinator

    @application.get("/api/v1/modules/job_scout/workspace")
    def get_workspace() -> JobScoutWorkspace:
        return coordinator.workspace()

    @application.put("/api/v1/modules/job_scout/config")
    def save_configuration(
        configuration: JobScoutConfiguration,
    ) -> JobScoutWorkspace:
        try:
            coordinator.save_configuration(configuration)
            return coordinator.workspace()
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @application.post(
        "/api/v1/modules/job_scout/resume",
        status_code=status.HTTP_201_CREATED,
    )
    async def load_resume(request: ResumeLoadRequest) -> JobScoutWorkspace:
        try:
            return await coordinator.load_resume(request)
        except (DocumentImportError, OSError) as error:
            detail = (
                {"code": error.code, "message": str(error)}
                if isinstance(error, DocumentImportError)
                else {
                    "code": "DOCUMENT_ACCESS_FAILED",
                    "message": "The file could not be read.",
                }
            )
            raise HTTPException(status_code=422, detail=detail) from error
        except ProviderError as error:
            raise HTTPException(status_code=503, detail=error.as_dict()) from error

    @application.post("/api/v1/modules/job_scout/keywords/discover")
    def refresh_keywords() -> JobScoutWorkspace:
        return coordinator.refresh_keywords()

    @application.post("/api/v1/modules/job_scout/scan")
    async def scan(request: JobScoutScanRequest) -> JobScoutScanSummary:
        return await coordinator.scan(request)

    return coordinator
