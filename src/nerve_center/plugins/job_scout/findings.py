"""Read-only Job Scout employer findings projection."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel, Field

from nerve_center.discovery.models import (
    Company,
    DiscoverySource,
    JobProvenance,
    NormalizedJobOpening,
    WorkArrangement,
)
from nerve_center.persistence.database import Database
from nerve_center.persistence.discovery import (
    CompanyRepository,
    DiscoverySourceRepository,
    JobOpeningRepository,
)
from nerve_center.persistence.scoring import (
    CompanyEnrichmentRepository,
    LocationPreferencesRepository,
    OpportunityScoreRepository,
)
from nerve_center.plugins.job_scout.settings import JobScoutConfigurationStore
from nerve_center.plugins.job_scout.verification import (
    VerificationStatus,
    assess_opening_verification,
    is_employer_authoritative_source,
)
from nerve_center.scoring.discovery_advantage import (
    DiscoveryAdvantageClass,
    assess_discovery_advantage,
)
from nerve_center.scoring.engine import SCORING_ENGINE_VERSION
from nerve_center.scoring.location import assess_location
from nerve_center.scoring.models import JobEnrichment, LocationScope, OpportunityScore
from nerve_center.scoring.service import _effective_location_preferences


class EmployerBestRole(BaseModel):
    job_id: str
    title: str
    priority: float
    fit: float
    resume_document_id: str | None = None
    resume_label: str | None = None
    discovery_advantage: str


class EmployerFinding(BaseModel):
    company: Company
    presence_scope: Literal["local", "regional", "distant", "unknown"]
    presence_confidence: float = Field(ge=0, le=1)
    presence_evidence: list[str] = Field(default_factory=list)
    career_source_health: str
    last_career_scan_at: datetime | None = None
    career_url: str | None = None
    current_actionable_roles: int = 0
    current_relevant_roles: int = 0
    relevant_roles_30d: int = 0
    relevant_roles_90d: int = 0
    direct_first_roles: int = 0
    direct_only_roles: int = 0
    secondary_first_verified_roles: int = 0
    broadly_syndicated_roles: int = 0
    unverified_leads: int = 0
    verified_absent_roles: int = 0
    best_role: EmployerBestRole | None = None


def register_job_scout_findings_routes(
    application: FastAPI,
    database: Database,
    configuration_store: JobScoutConfigurationStore,
) -> None:
    companies = CompanyRepository(database)
    sources = DiscoverySourceRepository(database)
    jobs = JobOpeningRepository(database)
    company_enrichment = CompanyEnrichmentRepository(database)
    location_preferences = LocationPreferencesRepository(database)
    scores = OpportunityScoreRepository(database)

    @application.get(
        "/api/v1/modules/job_scout/findings/employers",
        response_model=list[EmployerFinding],
    )
    def employer_findings() -> list[EmployerFinding]:
        configuration = configuration_store.load()
        preferences = _effective_location_preferences(
            location_preferences.get(),
            configuration.locations,
        )
        openings = jobs.list(active_only=False)
        all_sources = sources.list()
        now = datetime.now(UTC)
        rows: list[EmployerFinding] = []
        for company in companies.list():
            company_openings = [
                opening for opening in openings if opening.company_id == company.id
            ]
            company_sources = [
                source
                for source in all_sources
                if source.company_id == company.id
                and is_employer_authoritative_source(source)
            ]
            enrichment = company_enrichment.get(company.id)
            presence = assess_location(
                work_arrangement=WorkArrangement.REMOTE,
                job_location=JobEnrichment(job_id=f"employer:{company.id}"),
                company=enrichment,
                preferences=preferences,
                listing_locations=[],
                listing_evidence=[],
            )
            presence_evidence = [
                office.evidence_url
                for office in enrichment.offices
                if office.relevant_to_function and office.evidence_url
            ]
            actionable = []
            relevant: list[tuple[NormalizedJobOpening, OpportunityScore]] = []
            unverified = 0
            verified_absent = 0
            direct_first = 0
            direct_only = 0
            secondary_first_verified = 0
            broadly_syndicated = 0
            for opening in company_openings:
                verification = assess_opening_verification(opening, sources)
                if verification.status is VerificationStatus.VERIFIED_ABSENT:
                    verified_absent += 1
                    continue
                actionable.append(opening)
                if verification.status is not VerificationStatus.VERIFIED_PRESENT:
                    unverified += 1
                advantage = assess_discovery_advantage(opening.provenance)
                if _direct_first(opening.provenance):
                    direct_first += 1
                if advantage.classification is DiscoveryAdvantageClass.DIRECT_ONLY:
                    direct_only += 1
                elif (
                    advantage.classification
                    is DiscoveryAdvantageClass.SECONDARY_FIRST_LATER_VERIFIED
                ):
                    secondary_first_verified += 1
                elif (
                    advantage.classification
                    is DiscoveryAdvantageClass.BROADLY_SYNDICATED
                ):
                    broadly_syndicated += 1
                current_scores = [
                    score
                    for score in scores.list(opening.id)
                    if score.calculation.get("scoring_engine_version")
                    == SCORING_ENGINE_VERSION
                ]
                if current_scores:
                    best_score = max(
                        current_scores,
                        key=lambda score: (score.priority, score.created_at),
                    )
                    if best_score.retained and not best_score.excluded:
                        relevant.append((opening, best_score))
            best = max(
                relevant,
                key=lambda item: (item[1].priority, item[1].fit),
                default=None,
            )
            recent_30 = now - timedelta(days=30)
            recent_90 = now - timedelta(days=90)
            relevant_30 = sum(
                opening.discovered_at >= recent_30 for opening, _score in relevant
            )
            relevant_90 = sum(
                opening.discovered_at >= recent_90 for opening, _score in relevant
            )
            rows.append(
                EmployerFinding(
                    company=company,
                    presence_scope=presence.scope.value,
                    presence_confidence=presence.confidence,
                    presence_evidence=list(dict.fromkeys(presence_evidence)),
                    career_source_health=_source_health(company_sources),
                    last_career_scan_at=max(
                        (
                            source.last_scan_at
                            for source in company_sources
                            if source.last_scan_at is not None
                        ),
                        default=None,
                    ),
                    career_url=company.career_url
                    or next(
                        (source.base_url for source in company_sources),
                        None,
                    ),
                    current_actionable_roles=len(actionable),
                    current_relevant_roles=len(relevant),
                    relevant_roles_30d=relevant_30,
                    relevant_roles_90d=relevant_90,
                    direct_first_roles=direct_first,
                    direct_only_roles=direct_only,
                    secondary_first_verified_roles=secondary_first_verified,
                    broadly_syndicated_roles=broadly_syndicated,
                    unverified_leads=unverified,
                    verified_absent_roles=verified_absent,
                    best_role=(
                        EmployerBestRole(
                            job_id=best[0].id,
                            title=best[0].title,
                            priority=best[1].priority,
                            fit=best[1].fit,
                            resume_document_id=best[1].resume_document_id,
                            resume_label=best[1].resume_label,
                            discovery_advantage=assess_discovery_advantage(
                                best[0].provenance
                            ).classification.value,
                        )
                        if best is not None
                        else None
                    ),
                )
            )
        rows.sort(key=_employer_sort_key)
        return rows


def _source_health(sources: list[DiscoverySource]) -> str:
    if not sources:
        return "unresolved"
    values = {source.health.value for source in sources}
    for value in ("healthy", "challenged", "blocked", "degraded", "unknown"):
        if value in values:
            return value
    return "unknown"


def _direct_first(provenance: list[JobProvenance]) -> bool:
    if not provenance:
        return False
    first = min(item.discovered_at for item in provenance)
    return any(
        item.discovered_at == first and item.direct_employer_source
        for item in provenance
    )


def _employer_sort_key(item: EmployerFinding) -> tuple[int, float, int, str]:
    scope_order = {
        LocationScope.LOCAL.value: 0,
        LocationScope.REGIONAL.value: 1,
        LocationScope.UNKNOWN.value: 2,
        LocationScope.DISTANT.value: 3,
    }
    return (
        scope_order.get(item.presence_scope, 4),
        -(item.best_role.priority if item.best_role else -1),
        -item.current_relevant_roles,
        item.company.canonical_name.casefold(),
    )
