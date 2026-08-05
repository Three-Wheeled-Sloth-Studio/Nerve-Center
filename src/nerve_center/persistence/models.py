"""SQLAlchemy persistence models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class RunModel(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(100), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    window_kind: Mapped[str] = mapped_column(String(16))
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    requested_starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    requested_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    configuration: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    checkpoint: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    budget: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    budget_usage: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    result_summary: Mapped[str | None] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(String(100))
    result_metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    session_id: Mapped[str | None] = mapped_column(
        ForeignKey("core_sessions.id"), nullable=True, index=True
    )
    module_priority: Mapped[int] = mapped_column(Integer, default=10)


class RunEventModel(Base):
    __tablename__ = "run_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    event_type: Mapped[str] = mapped_column(String(50))
    source_status: Mapped[str | None] = mapped_column(String(32))
    target_status: Mapped[str | None] = mapped_column(String(32))
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class ModuleModel(Base):
    __tablename__ = "core_modules"

    module_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    lifecycle_state: Mapped[str] = mapped_column(String(32), index=True)
    saved_priority: Mapped[int] = mapped_column(Integer, default=10)
    manifest: Mapped[dict[str, Any]] = mapped_column(JSON)
    installed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class WorkSessionModel(Base):
    __tablename__ = "core_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    admission_phase: Mapped[str] = mapped_column(String(32), index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recurrence: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    recurrence_parent_id: Mapped[str | None] = mapped_column(String(36), index=True)
    module_run_ids: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    module_priorities: Mapped[dict[str, int]] = mapped_column(JSON, default=dict)
    resource_policy: Mapped[dict[str, int]] = mapped_column(JSON, default=dict)
    emergency_stop: Mapped[bool] = mapped_column(Boolean, default=False)
    result_summary: Mapped[str | None] = mapped_column(Text)


class WorkRequestModel(Base):
    __tablename__ = "core_work_requests"
    __table_args__ = (
        UniqueConstraint("module_id", "idempotency_key", name="uq_work_request_idempotency"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    module_id: Mapped[str] = mapped_column(String(100), index=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    session_id: Mapped[str | None] = mapped_column(
        ForeignKey("core_sessions.id"), nullable=True, index=True
    )
    task_id: Mapped[str] = mapped_column(String(100), index=True)
    work_class: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    output_contract: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    requirements: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    idempotency_key: Mapped[str] = mapped_column(String(255))
    module_priority: Mapped[int] = mapped_column(Integer)
    task_priority: Mapped[int] = mapped_column(Integer)
    max_retries: Mapped[int] = mapped_column(Integer)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(100))


class WorkAttemptModel(Base):
    __tablename__ = "core_work_attempts"
    __table_args__ = (UniqueConstraint("request_id", "number", name="uq_work_attempt_number"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    request_id: Mapped[str] = mapped_column(ForeignKey("core_work_requests.id"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), index=True)
    worker_id: Mapped[str] = mapped_column(String(100), index=True)
    claimed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(100))
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class WorkResultModel(Base):
    __tablename__ = "core_work_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    request_id: Mapped[str] = mapped_column(
        ForeignKey("core_work_requests.id"), unique=True, index=True
    )
    attempt_id: Mapped[str] = mapped_column(ForeignKey("core_work_attempts.id"), index=True)
    module_id: Mapped[str] = mapped_column(String(100), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivery_count: Mapped[int] = mapped_column(Integer, default=0)
    last_delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SourceDocumentModel(Base):
    __tablename__ = "source_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_path: Mapped[str] = mapped_column(Text)
    file_name: Mapped[str] = mapped_column(String(255))
    format: Mapped[str] = mapped_column(String(32))
    media_type: Mapped[str] = mapped_column(String(150))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    byte_size: Mapped[int] = mapped_column(Integer)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    segments: Mapped[list[dict[str, str]]] = mapped_column(JSON, default=list)


class CareerProfileModel(Base):
    __tablename__ = "career_profiles"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    version: Mapped[int] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class ProviderCallModel(Base):
    __tablename__ = "provider_calls"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    provider: Mapped[str] = mapped_column(String(50), index=True)
    model: Mapped[str] = mapped_column(String(200), index=True)
    contract_version: Mapped[str] = mapped_column(String(100))
    response_schema: Mapped[str] = mapped_column(String(100))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    duration_ms: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), index=True)
    error_code: Mapped[str | None] = mapped_column(String(100))
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    input_char_count: Mapped[int] = mapped_column(Integer, default=0)
    output_char_count: Mapped[int] = mapped_column(Integer, default=0)
    prompt_eval_count: Mapped[int | None] = mapped_column(Integer)
    eval_count: Mapped[int | None] = mapped_column(Integer)


class ProviderModelCatalogModel(Base):
    __tablename__ = "provider_model_catalog"
    __table_args__ = (UniqueConstraint("provider", "model", name="uq_provider_model_catalog"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    provider: Mapped[str] = mapped_column(String(50), index=True)
    model: Mapped[str] = mapped_column(String(200), index=True)
    label: Mapped[str] = mapped_column(String(200))
    family: Mapped[str | None] = mapped_column(String(100))
    parameter_size: Mapped[str | None] = mapped_column(String(100))
    quantization: Mapped[str | None] = mapped_column(String(100))
    provider_modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    installed: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    capabilities: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    hardware_fit: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ModelObservationModel(Base):
    __tablename__ = "model_observations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    provider_call_id: Mapped[str | None] = mapped_column(String(36), unique=True, index=True)
    work_request_id: Mapped[str | None] = mapped_column(String(36), index=True)
    task_id: Mapped[str] = mapped_column(String(100), index=True)
    provider: Mapped[str] = mapped_column(String(50), index=True)
    model: Mapped[str] = mapped_column(String(200), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    duration_ms: Mapped[int] = mapped_column(Integer)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    schema_valid: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    accepted: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    disposition_reason: Mapped[str | None] = mapped_column(String(1000))
    error_code: Mapped[str | None] = mapped_column(String(100))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class CompanyModel(Base):
    __tablename__ = "companies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    canonical_name: Mapped[str] = mapped_column(String(255), index=True)
    domain: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    career_url: Mapped[str | None] = mapped_column(Text)
    ats_type: Mapped[str | None] = mapped_column(String(50), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class DiscoverySourceModel(Base):
    __tablename__ = "discovery_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str | None] = mapped_column(ForeignKey("companies.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    kind: Mapped[str] = mapped_column(String(50), index=True)
    acquisition_class: Mapped[str] = mapped_column(String(50), index=True)
    base_url: Mapped[str] = mapped_column(Text)
    configuration: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    parser_version: Mapped[str] = mapped_column(String(100))
    scan_interval_minutes: Mapped[int] = mapped_column(Integer)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    health: Mapped[str] = mapped_column(String(32), index=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_scan_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    next_scan_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    challenge_count: Mapped[int] = mapped_column(Integer, default=0)
    rate_limit_count: Mapped[int] = mapped_column(Integer, default=0)
    policy_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SourceScanModel(Base):
    __tablename__ = "source_scans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("discovery_sources.id"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    requests_made: Mapped[int] = mapped_column(Integer)
    openings_found: Mapped[int] = mapped_column(Integer)
    http_status: Mapped[int | None] = mapped_column(Integer)
    safe_detail: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class JobOpeningModel(Base):
    __tablename__ = "job_openings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    title: Mapped[str] = mapped_column(String(500), index=True)
    canonical_url: Mapped[str] = mapped_column(Text, index=True)
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    external_id: Mapped[str | None] = mapped_column(String(255), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    first_discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)


class JobProvenanceModel(Base):
    __tablename__ = "job_provenance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("job_openings.id"), index=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("discovery_sources.id"), index=True)
    connector: Mapped[str] = mapped_column(String(50), index=True)
    parser_version: Mapped[str] = mapped_column(String(100))
    source_url: Mapped[str] = mapped_column(Text)
    external_id: Mapped[str | None] = mapped_column(String(255))
    direct_employer_source: Mapped[bool] = mapped_column(Boolean, default=False)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class SearchCacheModel(Base):
    __tablename__ = "search_cache"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider: Mapped[str] = mapped_column(String(50), index=True)
    query: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)


class LocationPreferencesModel(Base):
    __tablename__ = "location_preferences"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    version: Mapped[int] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)


class CompanyEnrichmentModel(Base):
    __tablename__ = "company_enrichment"

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), primary_key=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)


class JobEnrichmentModel(Base):
    __tablename__ = "job_enrichment"

    job_id: Mapped[str] = mapped_column(ForeignKey("job_openings.id"), primary_key=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)


class FitAnalysisModel(Base):
    __tablename__ = "fit_analyses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("job_openings.id"), index=True)
    profile_version: Mapped[int] = mapped_column(Integer, index=True)
    contract_version: Mapped[str] = mapped_column(String(100), index=True)
    model: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)


class ScoringSettingsModel(Base):
    __tablename__ = "scoring_settings"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    version: Mapped[int] = mapped_column(Integer)
    contract_version: Mapped[str] = mapped_column(String(100), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)


class ScoringRuleModel(Base):
    __tablename__ = "scoring_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    target: Mapped[str] = mapped_column(String(50), index=True)
    action: Mapped[str] = mapped_column(String(50), index=True)
    pattern: Mapped[str] = mapped_column(String(500), index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)


class OpportunityScoreModel(Base):
    __tablename__ = "opportunity_scores"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("job_openings.id"), index=True)
    profile_version: Mapped[int] = mapped_column(Integer, index=True)
    contract_version: Mapped[str] = mapped_column(String(100), index=True)
    settings_version: Mapped[int] = mapped_column(Integer, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    priority: Mapped[float] = mapped_column()
    excluded: Mapped[bool] = mapped_column(Boolean, index=True)
    retained: Mapped[bool] = mapped_column(Boolean, index=True)
    calibration_key: Mapped[str] = mapped_column(String(100), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
