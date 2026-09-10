"""Application service for fit analysis and append-only opportunity scoring."""

from __future__ import annotations

import re
from collections.abc import Callable
from uuid import NAMESPACE_URL, uuid4, uuid5

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
from nerve_center.scoring.location import infer_job_location
from nerve_center.scoring.models import (
    CompanyEnrichment,
    JobFitAnalysis,
    LocationPreferences,
    OfficeLocation,
    OpportunityScore,
)


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
        target_titles_provider: Callable[[], list[str]] | None = None,
        location_markets_provider: Callable[[], list[str]] | None = None,
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
        self.target_titles_provider = target_titles_provider
        self.location_markets_provider = location_markets_provider
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
        stored_company_enrichment = self.company_enrichment.get(opening.company_id)
        company_enrichment = _merge_observed_company_presence(
            stored_company_enrichment,
            self.jobs.list(active_only=False),
        )
        if company_enrichment.offices != stored_company_enrichment.offices:
            company_enrichment = self.company_enrichment.save(company_enrichment)
        location_preferences = _effective_location_preferences(
            self.location_preferences.get(),
            self.location_markets_provider() if self.location_markets_provider else [],
        )
        stored_job_enrichment = self.job_enrichment.get(job_id)
        inferred_job_enrichment = infer_job_location(opening)
        job_enrichment = stored_job_enrichment.model_copy(
            update={
                "location_labels": stored_job_enrichment.location_labels
                or inferred_job_enrichment.location_labels,
                "region": stored_job_enrichment.region or inferred_job_enrichment.region,
                "country": stored_job_enrichment.country or inferred_job_enrichment.country,
                "location_confidence": (
                    stored_job_enrichment.location_confidence
                    if stored_job_enrichment.location_labels
                    else inferred_job_enrichment.location_confidence
                ),
            }
        )
        if job_enrichment.model_dump(exclude={"updated_at"}) != (
            stored_job_enrichment.model_dump(exclude={"updated_at"})
        ):
            job_enrichment = self.job_enrichment.save(job_enrichment)
        result = self.scorer.score(
            opening=opening,
            profile=profile,
            fit_analysis=analysis,
            company_enrichment=company_enrichment,
            job_enrichment=job_enrichment,
            location_preferences=location_preferences,
            settings=self.settings.get(),
            rules=self.rules.list(enabled_only=True),
            target_title_alignment=_title_role_alignment(
                opening.title,
                self.target_titles_provider() if self.target_titles_provider else [],
            ),
        )
        return self.scores.append(result)


    def ensure_provisional_score(
        self,
        job_id: str,
        *,
        intent_terms: list[str],
        target_titles: list[str] | None = None,
    ) -> OpportunityScore:
        provisional_contract = "job-fit-provisional-v4"
        existing = self.scores.list(job_id)
        if existing:
            recorded_contract = existing[0].calculation.get("fit_contract_version")
            if recorded_contract and not str(recorded_contract).startswith(
                "job-fit-provisional-"
            ):
                return existing[0]
            if recorded_contract == provisional_contract:
                return existing[0]
            try:
                latest_analysis = self.fit_analyses.latest(job_id)
            except KeyError:
                latest_analysis = None
            if latest_analysis and not latest_analysis.contract_version.startswith(
                "job-fit-provisional-"
            ):
                return existing[0]
        opening = _get_job(self.jobs, job_id)
        profile = self.profiles.get_profile()
        haystack = _tokens(f"{opening.title} {opening.description}")
        intent = _tokens(" ".join(intent_terms))
        profile_terms = _tokens(
            " ".join(
                f"{claim.label} {claim.statement}"
                for claim in profile.claims
                if claim.decision.value != "rejected"
            )
        )
        overlap = len(haystack & intent) / max(1, len(intent))
        evidence_overlap = len(haystack & profile_terms) / max(1, len(profile_terms))
        role_alignment = _title_role_alignment(opening.title, target_titles or intent_terms)
        baseline = min(
            88.0,
            20.0 + role_alignment * 50.0 + overlap * 10.0 + evidence_overlap * 30.0,
        )
        if role_alignment < 0.5:
            baseline = min(baseline, 25.0)
        analysis = JobFitAnalysis(
            id=str(uuid4()),
            job_id=job_id,
            profile_version=profile.version,
            contract_version=provisional_contract,
            model="deterministic-provisional",
            seniority_score=min(90.0, 25.0 + role_alignment * 65.0),
            domain_score=baseline,
            leadership_score=baseline,
            methods_score=baseline,
            outcomes_score=baseline,
            confidence=0.35,
            review_notes=[
                "Provisional score uses configured target-title alignment, search intent, and "
                "persisted career-evidence overlap; run fit analysis for requirement-level "
                "evidence."
            ],
        )
        self.fit_analyses.save(analysis)
        return self.score(job_id, fit_analysis_id=analysis.id)


def _effective_location_preferences(
    preferences: LocationPreferences,
    configured_markets: list[str],
) -> LocationPreferences:
    markets = list(dict.fromkeys([*preferences.local_markets, *configured_markets]))
    home_label = preferences.home_label or (markets[0] if markets else None)
    configured_regions = [
        region for market in markets if (region := _location_region(market))
    ]
    return preferences.model_copy(
        update={
            "local_markets": markets,
            "home_label": home_label,
            "home_region": preferences.home_region
            or (configured_regions[0] if configured_regions else None),
            "regional_regions": list(
                dict.fromkeys([*preferences.regional_regions, *configured_regions])
            ),
        }
    )


def _merge_observed_company_presence(
    enrichment: CompanyEnrichment,
    openings: list[NormalizedJobOpening],
) -> CompanyEnrichment:
    offices = list(enrichment.offices)
    known = {_normalize_location_label(office.label) for office in offices}
    for opening in openings:
        if opening.company_id != enrichment.company_id or not any(
            item.direct_employer_source for item in opening.provenance
        ):
            continue
        for label in _specific_presence_locations(opening):
            normalized = _normalize_location_label(label)
            if normalized in known:
                continue
            offices.append(
                OfficeLocation(
                    id=str(uuid5(NAMESPACE_URL, f"{enrichment.company_id}:{normalized}")),
                    label=label,
                    region=_location_region(label),
                    evidence_url=opening.canonical_url,
                    confidence=round(opening.parser_confidence * 0.85, 4),
                )
            )
            known.add(normalized)
    return enrichment.model_copy(update={"offices": offices})


def _specific_presence_locations(opening: NormalizedJobOpening) -> list[str]:
    candidates = [*opening.locations]
    if opening.location_text:
        candidates.append(opening.location_text)
    results: list[str] = []
    for candidate in candidates:
        label = " ".join(candidate.split())
        normalized = _normalize_location_label(label)
        if not normalized or _is_generic_location(normalized):
            continue
        if normalized not in {_normalize_location_label(item) for item in results}:
            results.append(label)
    return results


def _normalize_location_label(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def _is_generic_location(normalized: str) -> bool:
    generic = {
        "anywhere",
        "global",
        "multiple locations",
        "nationwide",
        "remote",
        "remote usa",
        "remote us",
        "united states",
        "us",
        "usa",
        "worldwide",
    }
    return normalized in generic


def _location_region(label: str) -> str | None:
    parts = [part.strip() for part in label.split(",")]
    if len(parts) < 2:
        return None
    region = re.sub(r"[^A-Za-z0-9 ]", "", parts[-1]).strip()
    return region or None


def _get_job(repository: JobOpeningRepository, job_id: str) -> NormalizedJobOpening:
    for opening in repository.list(active_only=False):
        if opening.id == job_id:
            return opening
    raise KeyError(f"unknown job opening: {job_id}")


_STOPWORDS = {
    "and",
    "are",
    "for",
    "from",
    "have",
    "into",
    "our",
    "that",
    "the",
    "their",
    "this",
    "with",
    "will",
    "you",
    "your",
}


def _tokens(value: str) -> set[str]:
    return {
        _normalize_token(token)
        for token in re.findall(r"[a-z0-9]+", value.casefold())
        if len(token) > 2 and token not in _STOPWORDS
    }


def _normalize_token(token: str) -> str:
    aliases = {
        "management": "manager",
        "products": "product",
    }
    return aliases.get(token, token)


def _title_role_alignment(title: str, target_titles: list[str]) -> float:
    title_tokens = _tokens(title)
    alignments = []
    for target in target_titles:
        target_tokens = _tokens(target)
        target_role = target_tokens - _GENERIC_TITLE_TOKENS
        title_role = title_tokens - _GENERIC_TITLE_TOKENS
        if target_role:
            union = title_role | target_role
            alignments.append(len(title_role & target_role) / max(1, len(union)))
    return max(alignments, default=1.0 if not target_titles else 0.0)


_GENERIC_TITLE_TOKENS = {
    "chief",
    "director",
    "head",
    "lead",
    "manager",
    "president",
    "principal",
    "senior",
    "vice",
}
