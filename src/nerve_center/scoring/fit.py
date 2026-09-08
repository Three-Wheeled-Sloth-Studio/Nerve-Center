"""Evidence-constrained local LLM analysis of job qualifications and career claims."""

from __future__ import annotations

import json
import re
from uuid import NAMESPACE_URL, uuid4, uuid5

from nerve_center.discovery.models import NormalizedJobOpening
from nerve_center.profile.models import CareerClaim, CanonicalCareerProfile, ClaimDecision
from nerve_center.providers.base import StructuredProvider
from nerve_center.scoring.models import (
    ExtractedQualificationAssessment,
    FitAnalysisResponse,
    JobFitAnalysis,
    MatchLevel,
    QualificationAssessment,
)

FIT_ANALYSIS_CONTRACT_VERSION = "job-fit-analysis-v4"

_SYSTEM_PROMPT = """Analyze job requirements only against supplied verified career claims.
Do not infer credentials, employers, education completion, licenses, clearances, or outcomes.
First select at most eight decision-relevant requirements or responsibilities from the job
description. Never use a career claim as a qualification or job excerpt.
Every qualification must cite a short, verbatim excerpt from the supplied job description.
Matched claim identifiers must exist in the supplied claim list.
A full or partial match requires at least one genuinely supporting career claim identifier.
A license or clearance gate may be marked only when the job explicitly requires it.
Return seniority, domain, leadership, methods, and outcomes scores on a 0-100 scale.
Return confidence on a 0-1 scale.
Return structured data matching the required schema."""


class JobFitAnalyzer:
    def __init__(self, provider: StructuredProvider) -> None:
        self.provider = provider

    async def analyze(
        self,
        opening: NormalizedJobOpening,
        profile: CanonicalCareerProfile,
        *,
        model: str | None = None,
    ) -> JobFitAnalysis:
        active_claims = [
            claim for claim in profile.claims if claim.decision is not ClaimDecision.REJECTED
        ]
        result = await self.provider.generate_structured(
            model=model or "auto",
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=_build_prompt(opening, active_claims),
            response_type=FitAnalysisResponse,
            contract_version=FIT_ANALYSIS_CONTRACT_VERSION,
        )
        return _validate_analysis(opening, profile, result.metadata.model, result.value)


def required_coverage(analysis: JobFitAnalysis) -> float:
    required = [item for item in analysis.qualifications if item.importance.value == "required"]
    if not required:
        return 0.5
    values = {
        MatchLevel.FULL: 1.0,
        MatchLevel.PARTIAL: 0.5,
        MatchLevel.NONE: 0.0,
        MatchLevel.UNKNOWN: 0.25,
    }
    return sum(values[item.match_level] for item in required) / len(required)


def preferred_coverage(analysis: JobFitAnalysis) -> float:
    preferred = [item for item in analysis.qualifications if item.importance.value == "preferred"]
    if not preferred:
        return 0.5
    values = {
        MatchLevel.FULL: 1.0,
        MatchLevel.PARTIAL: 0.5,
        MatchLevel.NONE: 0.0,
        MatchLevel.UNKNOWN: 0.25,
    }
    return sum(values[item.match_level] for item in preferred) / len(preferred)


def _build_prompt(opening: NormalizedJobOpening, claims: list[CareerClaim]) -> str:
    claim_payload = [claim.model_dump(mode="json") for claim in claims]
    return "\n".join(
        [
            "Verified career claims:",
            json.dumps(claim_payload, ensure_ascii=True),
            f"Job title: {opening.title}",
            "Job description:",
            opening.description,
            "Extract job requirements from the Job description section only, then compare each",
            "against the Verified career claims section. Assess seniority, domain, leadership,",
            "methods, and outcome alignment. Use only verbatim job excerpts and listed claim IDs.",
        ]
    )


def _validate_analysis(
    opening: NormalizedJobOpening,
    profile: CanonicalCareerProfile,
    model: str,
    response: FitAnalysisResponse,
) -> JobFitAnalysis:
    valid_claims = {
        claim.id: claim
        for claim in profile.claims
        if claim.decision is not ClaimDecision.REJECTED
    }
    description = " ".join(opening.description.casefold().split())
    qualifications: list[QualificationAssessment] = []
    review_notes: list[str] = []
    for index, extracted in enumerate(response.qualifications):
        qualifications.append(
            _validated_qualification(
                opening.id,
                index,
                extracted,
                valid_claims,
                description,
                review_notes,
            )
        )
    dimension_scores = [
        response.seniority_score,
        response.domain_score,
        response.leadership_score,
        response.methods_score,
        response.outcomes_score,
    ]
    if dimension_scores and max(dimension_scores) <= 1:
        dimension_scores = [item * 100 for item in dimension_scores]
        review_notes.append("Normalized model fit dimensions from a 0-1 scale to 0-100.")
    supported_qualifications = sum(
        bool(item.matched_claim_ids)
        and item.match_level in {MatchLevel.FULL, MatchLevel.PARTIAL}
        for item in qualifications
    )
    confidence = response.confidence
    if supported_qualifications == 0:
        dimension_scores = [
            min(dimension_scores[0], 60),
            min(dimension_scores[1], 35),
            min(dimension_scores[2], 40),
            min(dimension_scores[3], 35),
            min(dimension_scores[4], 35),
        ]
        confidence = min(confidence, 0.35)
        review_notes.append(
            "Capped unsupported fit dimensions because no qualification had verified career "
            "evidence."
        )
    analysis_id = str(uuid4())
    return JobFitAnalysis(
        id=analysis_id,
        job_id=opening.id,
        profile_version=profile.version,
        contract_version=FIT_ANALYSIS_CONTRACT_VERSION,
        model=model,
        qualifications=qualifications,
        seniority_score=dimension_scores[0],
        domain_score=dimension_scores[1],
        leadership_score=dimension_scores[2],
        methods_score=dimension_scores[3],
        outcomes_score=dimension_scores[4],
        confidence=confidence,
        review_notes=review_notes,
    )


def _validated_qualification(
    job_id: str,
    index: int,
    extracted: ExtractedQualificationAssessment,
    valid_claims: dict[str, CareerClaim],
    normalized_description: str,
    review_notes: list[str],
) -> QualificationAssessment:
    excerpt = " ".join(extracted.job_excerpt.casefold().split())
    excerpt_valid = excerpt in normalized_description
    claim_ids = [item for item in extracted.matched_claim_ids if item in valid_claims]
    invalid_claim_count = len(extracted.matched_claim_ids) - len(claim_ids)
    match_level = extracted.match_level
    confidence = extracted.confidence
    notes = extracted.notes
    if not excerpt_valid:
        match_level = MatchLevel.UNKNOWN
        confidence = min(confidence, 0.2)
        notes = "The model citation was not found in the job description."
        review_notes.append(f"Qualification {index + 1} had invalid job evidence.")
    if invalid_claim_count:
        confidence = min(confidence, 0.5)
        review_notes.append(f"Qualification {index + 1} cited unknown career claims.")
    if match_level in {MatchLevel.FULL, MatchLevel.PARTIAL} and not claim_ids:
        match_level = MatchLevel.UNKNOWN
        confidence = min(confidence, 0.3)
        review_notes.append(f"Qualification {index + 1} had no valid supporting claim.")
    if excerpt_valid and not claim_ids and match_level is MatchLevel.UNKNOWN:
        inferred = _infer_claim_matches(extracted.requirement, valid_claims)
        if inferred:
            claim_ids = inferred
            match_level = MatchLevel.PARTIAL
            confidence = min(max(confidence, 0.45), 0.6)
            notes = "Deterministic lexical evidence linked a persisted career claim."
            review_notes.append(
                f"Qualification {index + 1} received a conservative lexical claim match."
            )
    item_id = str(uuid5(NAMESPACE_URL, f"qualification|{job_id}|{index}|{extracted.requirement}"))
    return QualificationAssessment(
        id=item_id,
        importance=extracted.importance,
        requirement=extracted.requirement.strip(),
        job_excerpt=extracted.job_excerpt.strip(),
        matched_claim_ids=claim_ids,
        match_level=match_level,
        confidence=confidence,
        gate_category=extracted.gate_category,
        notes=notes,
    )


_MATCH_STOPWORDS = {
    "and",
    "experience",
    "for",
    "from",
    "into",
    "knowledge",
    "of",
    "the",
    "to",
    "using",
    "with",
    "years",
}


def _infer_claim_matches(
    requirement: str,
    claims: dict[str, CareerClaim],
) -> list[str]:
    required = _match_tokens(requirement)
    if len(required) < 2:
        return []
    scored: list[tuple[float, str]] = []
    for claim_id, claim in claims.items():
        evidence = _match_tokens(f"{claim.label} {claim.statement}")
        shared = required & evidence
        coverage = len(shared) / len(required)
        if len(shared) >= 2 and coverage >= 0.5:
            scored.append((coverage, claim_id))
    return [claim_id for _score, claim_id in sorted(scored, reverse=True)[:2]]


def _match_tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", value.casefold())
        if len(token) > 2 and token not in _MATCH_STOPWORDS
    }
