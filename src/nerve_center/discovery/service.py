"""Discovery source execution, persistence, and sitemap handoff."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

import httpx

from nerve_center.discovery.connectors import (
    GreenhouseConnector,
    JsonLdJobConnector,
    LeverConnector,
    SitemapConnector,
)
from nerve_center.discovery.connectors.base import JobSourceConnector
from nerve_center.discovery.fetching import DomainRequestGate, HttpFetcher
from nerve_center.discovery.models import (
    AcquisitionClass,
    Company,
    ConnectorScanResult,
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
from nerve_center.persistence.discovery import (
    CompanyRepository,
    DiscoverySourceRepository,
    JobOpeningRepository,
)


class FetcherFactory(Protocol):
    def __call__(
        self,
        before_request: Callable[[], object] | None = None,
    ) -> HttpFetcher: ...


class ConnectorRegistry:
    def __init__(self) -> None:
        self._connectors: dict[SourceKind, JobSourceConnector] = {}

    def register(self, kind: SourceKind, connector: JobSourceConnector) -> None:
        self._connectors[kind] = connector

    def get(self, kind: SourceKind) -> JobSourceConnector:
        try:
            return self._connectors[kind]
        except KeyError as error:
            raise KeyError(f"no connector registered for source kind: {kind}") from error

    @classmethod
    def defaults(cls) -> ConnectorRegistry:
        registry = cls()
        registry.register(SourceKind.GREENHOUSE, GreenhouseConnector())
        registry.register(SourceKind.LEVER, LeverConnector())
        registry.register(SourceKind.JSON_LD, JsonLdJobConnector())
        registry.register(SourceKind.SITEMAP, SitemapConnector())
        return registry


class DiscoveryService:
    def __init__(
        self,
        companies: CompanyRepository,
        sources: DiscoverySourceRepository,
        jobs: JobOpeningRepository,
        *,
        connectors: ConnectorRegistry | None = None,
        fetcher_factory: FetcherFactory | None = None,
    ) -> None:
        self.companies = companies
        self.sources = sources
        self.jobs = jobs
        self.connectors = connectors or ConnectorRegistry.defaults()
        shared_gate = DomainRequestGate(1)
        self.fetcher_factory = fetcher_factory or (
            lambda before_request=None: HttpFetcher(
                gate=shared_gate,
                before_request=before_request,
            )
        )

    async def scan_source(
        self,
        source_id: str,
        *,
        before_request: Callable[[], object] | None = None,
    ) -> ConnectorScanResult:
        source = self.sources.get(source_id)
        if not source.enabled or source.acquisition_class is AcquisitionClass.BLOCKED:
            raise ValueError("discovery source is disabled or blocked")
        if source.company_id is None:
            raise ValueError("direct discovery sources require a company")
        company = self.companies.get(source.company_id)
        connector = self.connectors.get(source.kind)
        started_at = datetime.now(UTC)
        try:
            result = await connector.scan(
                company,
                source,
                self.fetcher_factory(before_request),
            )
        except httpx.TimeoutException:
            result = ConnectorScanResult(
                status=ScanStatus.ACCESS_FAILED,
                safe_detail={"error_code": "SOURCE_TIMEOUT"},
            )
        except httpx.RequestError:
            result = ConnectorScanResult(
                status=ScanStatus.ACCESS_FAILED,
                safe_detail={"error_code": "SOURCE_UNREACHABLE"},
            )
        except (KeyError, TypeError, ValueError) as error:
            result = ConnectorScanResult(
                status=ScanStatus.PARSER_FAILED,
                safe_detail={
                    "error_code": "SOURCE_CONFIGURATION_OR_PARSE_FAILED",
                    "message": str(error)[:300],
                },
            )
        for opening in result.openings:
            self.jobs.upsert(opening)
        if source.kind is SourceKind.SITEMAP and result.discovered_urls:
            self._register_sitemap_urls(source, result.discovered_urls)
        finished_at = datetime.now(UTC)
        self.sources.record_scan(
            source_id,
            started_at=started_at,
            finished_at=finished_at,
            status=result.status,
            requests_made=result.requests_made,
            openings_found=len(result.openings),
            http_status=result.http_status,
            safe_detail=result.safe_detail,
        )
        return result

    def register_direct_career_url(self, url: str, title: str = "") -> DiscoverySource:
        del title
        url = canonicalize_url(url)
        domain = canonical_domain(url)
        if not domain:
            raise ValueError("A valid employer domain is required.")
        now = datetime.now(UTC)
        company = self.companies.upsert(
            Company(
                id=stable_company_id(domain),
                canonical_name=domain,
                domain=domain,
                career_url=url,
                created_at=now,
                updated_at=now,
            )
        )
        source = DiscoverySource(
            id=stable_source_id(SourceKind.JSON_LD.value, url),
            company_id=company.id,
            name=f"Direct career page: {url}",
            kind=SourceKind.JSON_LD,
            acquisition_class=AcquisitionClass.PUBLIC_HTML_ALLOWED,
            base_url=url,
            parser_version=JsonLdJobConnector.parser_version,
            scan_interval_minutes=1440,
            policy_notes="Discovered through broad unauthenticated web search.",
        )
        return self.sources.upsert(source)

    def _register_sitemap_urls(self, source: DiscoverySource, urls: list[str]) -> None:
        maximum = min(
            max(int(source.configuration.get("auto_register_limit") or 250), 1),
            5000,
        )
        interval = max(int(source.configuration.get("page_scan_interval_minutes") or 1440), 60)
        for url in urls[:maximum]:
            is_sitemap = "sitemap" in url.casefold() or url.casefold().endswith(".xml")
            kind = SourceKind.SITEMAP if is_sitemap else SourceKind.JSON_LD
            parser_version = (
                SitemapConnector.parser_version if is_sitemap else JsonLdJobConnector.parser_version
            )
            source_id = stable_source_id(kind.value, url)
            self.sources.upsert(
                DiscoverySource(
                    id=source_id,
                    company_id=source.company_id,
                    name=f"Discovered {kind.value}: {url}",
                    kind=kind,
                    acquisition_class=(
                        AcquisitionClass.PUBLIC_STRUCTURED_FEED
                        if is_sitemap
                        else AcquisitionClass.PUBLIC_HTML_ALLOWED
                    ),
                    base_url=url,
                    parser_version=parser_version,
                    scan_interval_minutes=interval,
                    policy_notes="Discovered through a public sitemap.",
                )
            )
