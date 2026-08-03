"""Normalized company, source, scan, and job-opening contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AcquisitionClass(StrEnum):
    OFFICIAL_API = "official_api"
    PUBLIC_STRUCTURED_FEED = "public_structured_feed"
    PUBLIC_HTML_ALLOWED = "public_html_allowed"
    BROWSER_ASSISTED_MANUAL = "browser_assisted_manual"
    MANUAL_IMPORT_ONLY = "manual_import_only"
    BLOCKED = "blocked"


class SourceKind(StrEnum):
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    JSON_LD = "json_ld"
    SITEMAP = "sitemap"
    DIRECT_HTML = "direct_html"
    WEB_SEARCH = "web_search"
    MANUAL = "manual"


class SourceHealth(StrEnum):
    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CHALLENGED = "challenged"
    BLOCKED = "blocked"


class ScanStatus(StrEnum):
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    CHALLENGED = "challenged"
    THROTTLED = "throttled"
    ACCESS_FAILED = "access_failed"
    PARSER_FAILED = "parser_failed"
    FAILED = "failed"


class WorkArrangement(StrEnum):
    UNKNOWN = "unknown"
    ON_SITE = "on_site"
    HYBRID = "hybrid"
    REMOTE = "remote"


class Company(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    canonical_name: str
    domain: str
    career_url: str | None = None
    ats_type: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DiscoverySource(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    company_id: str | None = None
    name: str
    kind: SourceKind
    acquisition_class: AcquisitionClass
    base_url: str
    configuration: dict[str, Any] = Field(default_factory=dict)
    parser_version: str
    scan_interval_minutes: int = Field(default=1440, ge=5)
    enabled: bool = True
    health: SourceHealth = SourceHealth.UNKNOWN
    last_success_at: datetime | None = None
    last_scan_at: datetime | None = None
    next_scan_at: datetime | None = None
    consecutive_failures: int = 0
    challenge_count: int = 0
    rate_limit_count: int = 0
    policy_notes: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class JobProvenance(BaseModel):
    source_id: str
    connector: str
    parser_version: str
    source_url: str
    external_id: str | None = None
    direct_employer_source: bool = False
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class NormalizedJobOpening(BaseModel):
    id: str
    company_id: str
    company_name: str
    company_domain: str
    title: str
    description: str
    location_text: str | None = None
    locations: list[str] = Field(default_factory=list)
    work_arrangement: WorkArrangement = WorkArrangement.UNKNOWN
    employment_type: str | None = None
    department: str | None = None
    team: str | None = None
    source_url: str
    canonical_url: str
    apply_url: str | None = None
    external_id: str | None = None
    posted_at: datetime | None = None
    updated_at: datetime | None = None
    valid_through: datetime | None = None
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    parser_confidence: float = Field(default=1.0, ge=0, le=1)
    active: bool = True
    provenance: list[JobProvenance] = Field(min_length=1)


class ConnectorScanResult(BaseModel):
    status: ScanStatus
    openings: list[NormalizedJobOpening] = Field(default_factory=list)
    discovered_urls: list[str] = Field(default_factory=list)
    requests_made: int = 0
    http_status: int | None = None
    safe_detail: dict[str, Any] = Field(default_factory=dict)


class SourceScanRecord(BaseModel):
    id: str
    source_id: str
    started_at: datetime
    finished_at: datetime
    status: ScanStatus
    requests_made: int
    openings_found: int
    http_status: int | None = None
    safe_detail: dict[str, Any] = Field(default_factory=dict)
