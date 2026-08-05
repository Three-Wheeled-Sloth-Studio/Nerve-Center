"""Application service for fit analysis and append-only opportunity scoring."""

from __future__ import annotations

from nerve_center.discovery.models import NormalizedJobOpening
from nerve_center.persistence.discovery import JobOpeningRepository
from nerve_center.persistence.profile import CareerProfileRepository
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
from nerve_center.scoring.engine import OpportunityScorer
from nerve_center.scoring.fit import JobFitAnalyzer
from nerve_center.scoring.models import JobFitAnalysis, OpportunityScore


class ScoringService:
    def __init__(
        self,
        *,
        jobs: JobOpeningRepository,
        profiles: CareerProfileRepository,
        company_enrichment: CompanyEnrichmentRepository,
        job_enrichment: JobEnrichmentRepository,
        location_preferences: LocationPreferencesRepository,
        fit_analyses: FitAnalysisRepository,
        settings: ScoringSettingsRepository,
        rules: ScoringRuleRepository,
        scores: OpportunityScoreRepository,
        provider: StructuredProvider,
    ) -> None:
        self.jobs = jobs
        self.profiles = profiles
        self.company_enrichment = company_enrichment
        self.job_enrichment = job_enrichment
        self.location_preferences = location_preferences
        self.fit_analyses = fit_analyses
        self.settings = settings
        self.rules = rules
        self.scores = scores
        self.fit_analyzer = JobFitAnalyzer(provider)
        self.scorer = OpportunityScorer()

    async def analyze_fit(self, job_id: str, *, model: str | None = None) -> JobFitAnalysis:
        opening = _get_job(self.jobs, job_id)
        profile = self.profiles.get_profile()
        analysis = await self.fit_analyzer.analyze(opening, profile, model=model)
        return self.fit_analyses.save(analysis)

    def score(
        self,
        job_id: str,
        *,
        fit_analysis_id: str | None = None,
    ) -> OpportunityScore:
        opening = _get_job(self.jobs, job_id)
        profile = self.profiles.get_profile()
        analysis = (
            self.fit_analyses.get(fit_analysis_id)
            if fit_analysis_id
            else self.fit_analyses.latest(job_id)
        )
        if analysis.job_id != job_id:
            raise ValueError("fit analysis belongs to a different job")
        result = self.scorer.score(
            opening=opening,
            profile=profile,
            fit_analysis=analysis,
            company_enrichment=self.company_enrichment.get(opening.company_id),
            job_enrichment=self.job_enrichment.get(job_id),
            location_preferences=self.location_preferences.get(),
            settings=self.settings.get(),
            rules=self.rules.list(enabled_only=True),
        )
        return self.scores.append(result)


def _get_job(repository: JobOpeningRepository, job_id: str) -> NormalizedJobOpening:
    for opening in repository.list(active_only=False):
        if opening.id == job_id:
            return opening
    raise KeyError(f"unknown job opening: {job_id}")
