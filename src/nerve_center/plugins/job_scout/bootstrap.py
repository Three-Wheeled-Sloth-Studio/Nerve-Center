"""Job Scout composition adapter for the Nerve Center manager."""

from dataclasses import dataclass

from fastapi import FastAPI, HTTPException
from sqlalchemy import select

from nerve_center.applications.api import register_application_routes
from nerve_center.config import Settings
from nerve_center.discovery.api import register_discovery_routes
from nerve_center.discovery.service import DiscoveryService
from nerve_center.domain.module import ModuleManifest
from nerve_center.persistence.database import Database
from nerve_center.persistence.discovery import (
    CompanyRepository,
    DiscoverySourceRepository,
    JobOpeningRepository,
)
from nerve_center.plugins.job_scout.attachment_discovery import (
    AttachmentAwareJobScoutDiscoveryLoop,
)
from nerve_center.plugins.job_scout.configuration import (
    register_job_scout_configuration_routes,
)
from nerve_center.plugins.job_scout.discovery_learning import (
    DiscoveryStrategyModel,
    StrategyAttemptModel,
)
from nerve_center.plugins.job_scout.discovery_quality import DiscoveryQualityRepository
from nerve_center.plugins.job_scout.manifest import job_scout_manifest
from nerve_center.plugins.job_scout.runtime import JobScoutOperationBridge
from nerve_center.plugins.job_scout.uploads import register_job_scout_upload_route
from nerve_center.profile.api import register_profile_routes
from nerve_center.providers.base import StructuredProvider
from nerve_center.scoring.api import register_scoring_routes

_REFERENCE_EVIDENCE_KEYS = (
    "reference_selection_evidence",
    "employer_reference_evidence",
    "attachment_reference_evidence",
)
_REFERENCE_STAGE_COUNTERS = (
    "search_results_returned",
    "reference_pages_inspected",
    "reference_cache_hits",
    "reference_fetches_deferred",
    "reference_network_fetches_attempted",
    "employer_candidates_discovered",
    "attachment_links_discovered",
    "attachment_fetches_attempted",
    "attachment_cache_hits",
    "attachment_fetches_deferred",
    "attachment_documents_parsed",
    "attachment_documents_unsupported_or_invalid",
    "attachment_employer_candidates_extracted",
)


@dataclass(frozen=True, slots=True)
class JobScoutModulePackage:
    manifest: ModuleManifest
    operation_bridge: JobScoutOperationBridge


def install_job_scout(
    application: FastAPI,
    database: Database,
    settings: Settings,
    provider: StructuredProvider | None,
) -> JobScoutModulePackage:
    company_repository = CompanyRepository(database)
    source_repository = DiscoverySourceRepository(database)
    job_repository = JobOpeningRepository(database)
    learning_repository = DiscoveryQualityRepository(database)
    application.state.job_scout_learning = learning_repository
    discovery_service = DiscoveryService(
        company_repository,
        source_repository,
        job_repository,
    )
    register_profile_routes(application, database, settings, provider)
    register_discovery_routes(application, database, settings, discovery_service)
    coordinator = register_job_scout_configuration_routes(
        application,
        database,
        settings,
        provider,
        discovery_service,
        company_repository,
        source_repository,
        job_repository,
    )
    scoring_service = register_scoring_routes(
        application,
        database,
        settings,
        provider,
        target_titles_provider=lambda: coordinator.store.load().target_titles,
        location_markets_provider=lambda: coordinator.store.load().locations,
    )
    discovery_loop = AttachmentAwareJobScoutDiscoveryLoop(
        settings,
        coordinator,
        discovery_service,
        company_repository,
        source_repository,
        job_repository,
        learning_repository,
    )
    _register_discovery_learning_routes(application, learning_repository)
    register_application_routes(
        application,
        database,
        scoring_service=scoring_service,
        configuration_store=coordinator.store,
    )
    register_job_scout_upload_route(application, settings)
    return JobScoutModulePackage(
        manifest=job_scout_manifest(),
        operation_bridge=JobScoutOperationBridge(
            discovery_service,
            source_repository,
            coordinator,
            learning_repository,
            discovery_loop,
            scoring_service,
        ),
    )


def _recent_reference_attempt_evidence(
    learning: DiscoveryQualityRepository,
    *,
    run_id: str | None = None,
    limit: int = 64,
) -> list[dict[str, object]]:
    """Return bounded reference diagnostics, optionally scoped to one run."""

    scan_limit = max(limit * 4, 64)
    evidence: list[dict[str, object]] = []
    with learning.database.session() as session:
        statement = select(
            StrategyAttemptModel,
            DiscoveryStrategyModel,
        ).join(
            DiscoveryStrategyModel,
            StrategyAttemptModel.strategy_id == DiscoveryStrategyModel.id,
        )
        if run_id is not None:
            statement = statement.where(StrategyAttemptModel.run_id == run_id)
        rows = session.execute(
            statement.order_by(StrategyAttemptModel.finished_at.desc()).limit(scan_limit)
        ).all()
        for attempt, strategy in rows:
            detail = attempt.detail if isinstance(attempt.detail, dict) else {}
            stages = detail.get("stages")
            if not isinstance(stages, dict) or not any(
                key in stages for key in _REFERENCE_EVIDENCE_KEYS
            ):
                continue
            dimensions = (
                strategy.dimensions if isinstance(strategy.dimensions, dict) else {}
            )
            row: dict[str, object] = {
                "attempt_id": attempt.id,
                "run_id": attempt.run_id,
                "strategy_id": attempt.strategy_id,
                "cycle": attempt.cycle,
                "phase": attempt.phase,
                "status": attempt.status,
                "finished_at": attempt.finished_at,
                "hypothesis_family": dimensions.get("hypothesis_family", "legacy"),
                "location": dimensions.get("location", ""),
                "anchor": dimensions.get("anchor", ""),
            }
            for key in _REFERENCE_STAGE_COUNTERS:
                if key in stages:
                    row[key] = stages[key]
            for key in _REFERENCE_EVIDENCE_KEYS:
                value = stages.get(key)
                if isinstance(value, list):
                    row[key] = value
            evidence.append(row)
            if len(evidence) >= limit:
                break
    return evidence


def _recent_public_search_attempt_evidence(
    learning: DiscoveryQualityRepository,
    *,
    run_id: str | None = None,
    limit: int = 128,
) -> list[dict[str, object]]:
    """Return bounded per-search provider/cache evidence, optionally scoped to one run."""

    scan_limit = max(limit * 2, 64)
    evidence: list[dict[str, object]] = []
    with learning.database.session() as session:
        statement = select(
            StrategyAttemptModel,
            DiscoveryStrategyModel,
        ).join(
            DiscoveryStrategyModel,
            StrategyAttemptModel.strategy_id == DiscoveryStrategyModel.id,
        )
        if run_id is not None:
            statement = statement.where(StrategyAttemptModel.run_id == run_id)
        rows = session.execute(
            statement.order_by(StrategyAttemptModel.finished_at.desc()).limit(scan_limit)
        ).all()
        for attempt, strategy in rows:
            detail = attempt.detail if isinstance(attempt.detail, dict) else {}
            events = detail.get("search_attempt_evidence")
            if not isinstance(events, list):
                continue
            dimensions = (
                strategy.dimensions if isinstance(strategy.dimensions, dict) else {}
            )
            for event in events:
                if not isinstance(event, dict):
                    continue
                evidence.append(
                    {
                        "attempt_id": attempt.id,
                        "run_id": attempt.run_id,
                        "strategy_id": attempt.strategy_id,
                        "cycle": attempt.cycle,
                        "phase": attempt.phase,
                        "finished_at": attempt.finished_at,
                        "hypothesis_family": dimensions.get(
                            "hypothesis_family", "legacy"
                        ),
                        "anchor": dimensions.get("anchor", ""),
                        "location": dimensions.get("location", ""),
                        "query": str(event.get("query") or ""),
                        "search_provider": str(event.get("search_provider") or ""),
                        "search_provider_fallback_used": bool(
                            event.get("search_provider_fallback_used", False)
                        ),
                        "search_transport": str(
                            event.get("search_transport") or ""
                        ),
                        "status": str(event.get("status") or ""),
                        "result_count": max(int(event.get("result_count") or 0), 0),
                    }
                )
                if len(evidence) >= limit:
                    return evidence
    return evidence


def _register_discovery_learning_routes(
    application: FastAPI,
    learning: DiscoveryQualityRepository,
) -> None:
    @application.get("/api/v1/modules/job_scout/discovery/strategies")
    def list_discovery_strategies() -> list[dict[str, object]]:
        families = {item.id: item for item in learning.list_strategy_families()}
        rows: list[dict[str, object]] = []
        for item in learning.list_strategies():
            family = families[item.family_id]
            rows.append({
                "id": item.id,
                "family_id": item.family_id,
                "family_learned_weight": family.learned_weight,
                "family_influence": family.influence,
                "family_attempts": family.attempts,
                "family_conditioned_yield": family.opportunities_retained,
                "dimensions": item.dimensions,
                "hypothesis_family": item.dimensions.get(
                    "hypothesis_family", "legacy"
                ),
                "source_domain": item.dimensions.get("source_domain", ""),
                "location": item.dimensions.get("location", ""),
                "origin": item.origin,
                "learned_weight": item.learned_weight,
                "influence": item.influence,
                "attempts": item.attempts,
                "results_examined": item.results_examined,
                "companies_discovered": item.companies_discovered,
                "career_sources_resolved": item.career_sources_resolved,
                "postings_inspected": item.postings_inspected,
                "opportunities_retained": item.opportunities_retained,
                "yield_scope": (
                    "location_conditioned"
                    if item.dimensions.get("location")
                    else "total"
                ),
                "positive_feedback": item.positive_feedback,
                "negative_feedback": item.negative_feedback,
                "challenge_count": item.challenge_count,
                "failure_count": item.failure_count,
                "last_attempt_at": item.last_attempt_at,
                "last_productive_at": item.last_productive_at,
            })
        return rows

    @application.get("/api/v1/modules/job_scout/discovery/audit")
    def get_discovery_audit(run_id: str | None = None) -> dict[str, object]:
        audit = dict(learning.discovery_audit())
        audit["reference_attempt_evidence"] = _recent_reference_attempt_evidence(
            learning,
            run_id=run_id,
        )
        audit["public_search_attempt_evidence"] = (
            _recent_public_search_attempt_evidence(
                learning,
                run_id=run_id,
            )
        )
        return audit

    @application.get("/api/v1/modules/job_scout/discovery/sessions/{run_id}")
    def get_discovery_session(run_id: str) -> object:
        try:
            return learning.session(run_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @application.get("/api/v1/modules/job_scout/discovery/sessions/{run_id}/reflections")
    def list_reflection_hypotheses(run_id: str) -> list[dict[str, object]]:
        return learning.reflection_hypotheses(run_id)
