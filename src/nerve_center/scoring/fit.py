"""Evidence-constrained local LLM analysis of job qualifications and career claims."""

from __future__ import annotations

import json
from uuid import NAMESPACE_URL, uuid4, uuid5

from nerve_center.discovery.models import NormalizedJobOpening
from nerve_center.profile.models import CareerClaim, CanonicalCareerProfile, ClaimDecision
from nerve_center.providers.base import StructuredProvider
from nerve_center.scoring.evidence import CareerEvidenceMatcher
from nerve_center.scoring.models import (
    DomainRelationship,
    ExtractedQualificationAssessment,
    FitAnalysisResponse,
    JobFitAnalysis,
    MatchLevel,
    QualificationAssessment,
    QualificationImportance,
    RequirementEvidenceMatch,
)
from nerve_center.scoring.qualification_importance import (
    normalize_qualifications,
    weighted_coverage,
)

FIT_ANALYSIS_CONTRACT_VERSION = "job-fit-analysis-v7"

_SYSTEM_PROMPT = """Analyze job requirements only against supplied verified career claims.
Do not infer credentials, employers, education completion, licenses, clearances, or outcomes.
First select at most eight decision-relevant requirements or responsibilities from the job
description. Never use a career claim as a qualification or job excerpt.
Every qualification must cite a short, verbatim excerpt from the supplied job description.
Matched claim identifiers must exist in the supplied claim list.
A full or partial match requires at least one genuinely supporting career claim identifier.
A license or clearance gate may be marked only when the job explicitly requires it.
For each qualification, return decision_weight_hint from 0.5 to 1.5 describing only how
central that item is to employer screening or day-to-day role success. Do not increase or
decrease decision weight based on how well the candidate matches it. Explicit must/minimum/
essential/core wording may justify a high hint; preferred/nice-to-have/bonus wording may
justify a low hint. Use 1.0 when centrality is not clear from job-side evidence.
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
    return weighted_coverage(
        analysis.qualifications, QualificationImportance.REQUIRED
    )[0]


def preferred_coverage(analysis: JobFitAnalysis) -> float:
    return weighted_coverage(
        analysis.qualifications, QualificationImportance.PREFERRED
    )[0]


def responsibility_coverage(analysis: JobFitAnalysis) -> float:
    return weighted_coverage(
        analysis.qualifications, QualificationImportance.RESPONSIBILITY
    )[0]


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
            "Set decision_weight_hint only from job-side centrality evidence, never candidate fit.",
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
    matcher = CareerEvidenceMatcher()
    qualifications: list[QualificationAssessment] = []
    review_notes: list[str] = []
    if len(response.qualifications) > 8:
        review_notes.append("Limited model output to eight decision-relevant qualifications.")
    for index, extracted in enumerate(response.qualifications[:8]):
        qualifications.append(
            _validated_qualification(
                opening.id,
                index,
                extracted,
                valid_claims,
                description,
                review_notes,
                matcher.match_requirement(extracted.requirement, valid_claims.values()),
            )
        )
    qualifications = normalize_qualifications(qualifications)
    duplicate_count = sum(item.duplicate_of is not None for item in qualifications)
    if duplicate_count:
        review_notes.append(
            f"Marked {duplicate_count} near-duplicate qualification(s) "
            "to prevent repeated fit credit."
        )
    evidence_matches = [
        match for qualification in qualifications for match in qualification.evidence_matches
    ]
    domain_assessment = matcher.assess_domain(
        opening,
        valid_claims.values(),
        evidence_matches,
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
    domain_scores = {
        DomainRelationship.DIRECT: 90.0,
        DomainRelationship.ADJACENT: 70.0,
        DomainRelationship.TRANSFERABLE: 48.0,
        DomainRelationship.MISMATCH: 18.0,
    }
    dimension_scores[1] = domain_scores[domain_assessment.relationship]
    review_notes.append(
        "Domain score derived from the evidence-backed "
        f"{domain_assessment.relationship.value} relationship."
    )
    supported_qualifications = sum(
        bool(item.matched_claim_ids)
        and item.match_level in {MatchLevel.FULL, MatchLevel.PARTIAL}
        for item in qualifications
        if item.duplicate_of is None
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
        domain_assessment=domain_assessment,
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
    evidence_matches: list[RequirementEvidenceMatch],
) -> QualificationAssessment:
    excerpt = " ".join(extracted.job_excerpt.casefold().split())
    excerpt_valid = excerpt in normalized_description
    known_claim_ids = [item for item in extracted.matched_claim_ids if item in valid_claims]
    supported_claim_ids = {item.claim_id for item in evidence_matches}
    claim_ids = [item for item in known_claim_ids if item in supported_claim_ids]
    invalid_claim_count = len(extracted.matched_claim_ids) - len(known_claim_ids)
    unsupported_claim_count = len(known_claim_ids) - len(claim_ids)
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
    if unsupported_claim_count:
        confidence = min(confidence, 0.5)
        review_notes.append(
            f"Qualification {index + 1} cited career claims without validated support."
        )
    if match_level in {MatchLevel.FULL, MatchLevel.PARTIAL} and not claim_ids:
        match_level = MatchLevel.UNKNOWN
        confidence = min(confidence, 0.3)
        review_notes.append(f"Qualification {index + 1} had no valid supporting claim.")
    if excerpt_valid and not claim_ids and match_level is MatchLevel.UNKNOWN:
        inferred = [item.claim_id for item in evidence_matches]
        if inferred:
            claim_ids = inferred
            match_level = MatchLevel.PARTIAL
            confidence = min(max(confidence, 0.45), 0.6)
            notes = "Deterministic semantic evidence linked a persisted career claim."
            review_notes.append(
                f"Qualification {index + 1} received a conservative semantic claim match."
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
        evidence_matches=[
            item for item in evidence_matches if item.claim_id in set(claim_ids)
        ],
        decision_weight=extracted.decision_weight_hint,
    )
