"""Evidence-constrained local LLM analysis of job qualifications and career claims."""

from __future__ import annotations

import json
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

FIT_ANALYSIS_CONTRACT_VERSION = "job-fit-analysis-v1"

_SYSTEM_PROMPT = """Analyze job requirements only against supplied verified career claims.
Do not infer credentials, employers, education completion, licenses, clearances, or outcomes.
Every qualification must cite an exact excerpt from the supplied job description.
Matched claim identifiers must exist in the supplied claim list.
A license or clearance gate may be marked only when the job explicitly requires it.
Return structured data matching the required schema."""


class JobFitAnalyzer:
    def __init__(self, provider: StructuredProvider) -> None:
        self.provider = provider

    async def analyze(
        self,
        opening: NormalizedJobOpening,
        profile: CanonicalCareerProfile,
        *,
        model: str,
    ) -> JobFitAnalysis:
        active_claims = [
            claim for claim in profile.claims if claim.decision is not ClaimDecision.REJECTED
        ]
        result = await self.provider.generate_structured(
            model=model,
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=_build_prompt(opening, active_claims),
            response_type=FitAnalysisResponse,
            contract_version=FIT_ANALYSIS_CONTRACT_VERSION,
        )
        return _validate_analysis(opening, profile, model, result.value)


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
            f"Job title: {opening.title}",
            "Job description:",
            opening.description,
            "Verified career claims:",
            json.dumps(claim_payload, ensure_ascii=True),
            "Assess required and preferred qualifications, responsibilities, seniority, domain,",
            "leadership, methods, and outcome alignment. Use only exact job excerpts and listed",
            "claim identifiers.",
        ]
    )


def _validate_analysis(
    opening: NormalizedJobOpening,
    profile: CanonicalCareerProfile,
    model: str,
    response: FitAnalysisResponse,
) -> JobFitAnalysis:
    valid_claim_ids = {
        claim.id for claim in profile.claims if claim.decision is not ClaimDecision.REJECTED
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
                valid_claim_ids,
                description,
                review_notes,
            )
        )
    analysis_id = str(uuid4())
    return JobFitAnalysis(
        id=analysis_id,
        job_id=opening.id,
        profile_version=profile.version,
        contract_version=FIT_ANALYSIS_CONTRACT_VERSION,
        model=model,
        qualifications=qualifications,
        seniority_score=response.seniority_score,
        domain_score=response.domain_score,
        leadership_score=response.leadership_score,
        methods_score=response.methods_score,
        outcomes_score=response.outcomes_score,
        confidence=response.confidence,
        review_notes=review_notes,
    )


def _validated_qualification(
    job_id: str,
    index: int,
    extracted: ExtractedQualificationAssessment,
    valid_claim_ids: set[str],
    normalized_description: str,
    review_notes: list[str],
) -> QualificationAssessment:
    excerpt = " ".join(extracted.job_excerpt.casefold().split())
    excerpt_valid = excerpt in normalized_description
    claim_ids = [item for item in extracted.matched_claim_ids if item in valid_claim_ids]
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
