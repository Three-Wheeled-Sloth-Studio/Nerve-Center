"""Local API routes for location enrichment, fit analysis, rules, and scores."""

from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Response, status
from pydantic import BaseModel, Field

from nerve_center.config import Settings
from nerve_center.persistence.database import Database
from nerve_center.persistence.discovery import CompanyRepository, JobOpeningRepository
from nerve_center.persistence.profile import CareerProfileRepository
from nerve_center.persistence.providers import ProviderCallRepository
from nerve_center.persistence.scoring import (
    CompanyEnrichmentRepository,
    FitAnalysisRepository,
    JobEnrichmentRepository,
    LocationPreferencesRepository,
    OpportunityScoreRepository,
    ScoringRuleRepository,
    ScoringSettingsRepository,
)
from nerve_center.providers.base import StructuredProvider
from nerve_center.providers.errors import ProviderError
from nerve_center.providers.ollama import OllamaProvider
from nerve_center.scoring.models import (
    CompanyEnrichment,
    JobEnrichment,
    JobFitAnalysis,
    LocationPreferences,
    OpportunityScore,
    RuleAction,
    RuleMatch,
    RuleTarget,
    ScoringRule,
    ScoringSettings,
)
from nerve_center.scoring.service import ScoringService


class FitAnalyzeRequest(BaseModel):
    model: str | None = Field(default=None, min_length=1, max_length=200)


class ScoreRequest(BaseModel):
    fit_analysis_id: str | None = Field(default=None, max_length=100)


class RuleCreateRequest(BaseModel):
    target: RuleTarget
    action: RuleAction
    pattern: str = Field(min_length=1, max_length=500)
    match: RuleMatch = RuleMatch.CONTAINS
    adjustment: float | None = Field(default=None, ge=-100, le=100)
    enabled: bool = True
    note: str | None = Field(default=None, max_length=1000)


def register_scoring_routes(
    application: FastAPI,
    database: Database,
    settings: Settings,
    provider: StructuredProvider | None = None,
    target_titles_provider: Callable[[], list[str]] | None = None,
    location_markets_provider: Callable[[], list[str]] | None = None,
) -> ScoringService:
    runtime_provider = provider or OllamaProvider(
        base_url=settings.ollama_base_url,
        timeout_seconds=settings.ollama_timeout_seconds,
        telemetry=ProviderCallRepository(database),
    )
    companies = CompanyRepository(database)
    jobs = JobOpeningRepository(database)
    location_repository = LocationPreferencesRepository(database)
    company_repository = CompanyEnrichmentRepository(database)
    job_repository = JobEnrichmentRepository(database)
    fit_repository = FitAnalysisRepository(database)
    settings_repository = ScoringSettingsRepository(database)
    rule_repository = ScoringRuleRepository(database)
    score_repository = OpportunityScoreRepository(database)
    service = ScoringService(
        jobs=jobs,
        profiles=CareerProfileRepository(database),
        company_enrichment=company_repository,
        job_enrichment=job_repository,
        location_preferences=location_repository,
        fit_analyses=fit_repository,
        settings=settings_repository,
        rules=rule_repository,
        scores=score_repository,
        provider=runtime_provider,
        target_titles_provider=target_titles_provider,
        location_markets_provider=location_markets_provider,
    )
    application.state.scoring_service = service

    @application.get("/api/v1/scoring/settings")
    def get_scoring_settings() -> ScoringSettings:
        return settings_repository.get()

    @application.put("/api/v1/scoring/settings")
    def save_scoring_settings(request: ScoringSettings) -> ScoringSettings:
        return settings_repository.save(request)

    @application.get("/api/v1/scoring/location-preferences")
    def get_location_preferences() -> LocationPreferences:
        return location_repository.get()

    @application.put("/api/v1/scoring/location-preferences")
    def save_location_preferences(request: LocationPreferences) -> LocationPreferences:
        return location_repository.save(request)

    @application.get("/api/v1/scoring/companies/{company_id}/enrichment")
    def get_company_enrichment(company_id: str) -> CompanyEnrichment:
        try:
            companies.get(company_id)
            return company_repository.get(company_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @application.put("/api/v1/scoring/companies/{company_id}/enrichment")
    def save_company_enrichment(
        company_id: str,
        request: CompanyEnrichment,
    ) -> CompanyEnrichment:
        try:
            companies.get(company_id)
            return company_repository.save(request.model_copy(update={"company_id": company_id}))
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @application.get("/api/v1/scoring/jobs/{job_id}/enrichment")
    def get_job_enrichment(job_id: str) -> JobEnrichment:
        _require_job(jobs, job_id)
        return job_repository.get(job_id)

    @application.put("/api/v1/scoring/jobs/{job_id}/enrichment")
    def save_job_enrichment(job_id: str, request: JobEnrichment) -> JobEnrichment:
        _require_job(jobs, job_id)
        return job_repository.save(request.model_copy(update={"job_id": job_id}))

    @application.get("/api/v1/scoring/rules")
    def list_rules() -> list[ScoringRule]:
        return rule_repository.list()

    @application.post("/api/v1/scoring/rules", status_code=status.HTTP_201_CREATED)
    def create_rule(request: RuleCreateRequest) -> ScoringRule:
        return rule_repository.upsert(ScoringRule(id=str(uuid4()), **request.model_dump()))

    @application.delete("/api/v1/scoring/rules/{rule_id}", status_code=204)
    def delete_rule(rule_id: str) -> Response:
        try:
            rule_repository.delete(rule_id)
            return Response(status_code=204)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @application.post("/api/v1/scoring/jobs/{job_id}/fit")
    async def analyze_fit(job_id: str, request: FitAnalyzeRequest) -> JobFitAnalysis:
        try:
            return await service.analyze_fit(job_id, model=request.model)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ProviderError as error:
            raise HTTPException(status_code=502, detail=error.as_dict()) from error

    @application.get("/api/v1/scoring/jobs/{job_id}/fit")
    def list_fit_analyses(job_id: str) -> list[JobFitAnalysis]:
        return fit_repository.list(job_id)

    @application.post("/api/v1/scoring/jobs/{job_id}/scores")
    def score_job(job_id: str, request: ScoreRequest) -> OpportunityScore:
        try:
            return service.score(job_id, fit_analysis_id=request.fit_analysis_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @application.get("/api/v1/scoring/jobs/{job_id}/scores")
    def list_scores(job_id: str) -> list[OpportunityScore]:
        return score_repository.list(job_id)

    return service


def _require_job(repository: JobOpeningRepository, job_id: str) -> None:
    if not any(item.id == job_id for item in repository.list(active_only=False)):
        raise HTTPException(status_code=404, detail=f"unknown job opening: {job_id}")
