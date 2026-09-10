from nerve_center.discovery.models import JobProvenance, NormalizedJobOpening
from nerve_center.profile.models import CanonicalCareerProfile
from nerve_center.scoring.fit import _validate_analysis
from nerve_center.scoring.models import (
    ExtractedQualificationAssessment,
    FitAnalysisResponse,
    JobFitAnalysis,
    MatchLevel,
    QualificationImportance,
)


def _opening() -> NormalizedJobOpening:
    return NormalizedJobOpening(
        id="job-importance",
        company_id="company",
        company_name="Example",
        company_domain="example.com",
        title="Director of Product",
        description=(
            "Candidates must lead enterprise analytics products. "
            "Lead enterprise analytics products across business units."
        ),
        source_url="https://example.com/job",
        canonical_url="https://example.com/job",
        provenance=[
            JobProvenance(
                source_id="source",
                connector="fixture",
                parser_version="v1",
                source_url="https://example.com/job",
                direct_employer_source=True,
            )
        ],
    )


def test_v7_analysis_normalizes_hint_and_duplicate_linkage() -> None:
    response = FitAnalysisResponse(
        qualifications=[
            ExtractedQualificationAssessment(
                importance=QualificationImportance.REQUIRED,
                requirement="Lead enterprise analytics products",
                job_excerpt="Candidates must lead enterprise analytics products.",
                match_level=MatchLevel.UNKNOWN,
                confidence=0.6,
                decision_weight_hint=0.5,
            ),
            ExtractedQualificationAssessment(
                importance=QualificationImportance.RESPONSIBILITY,
                requirement="Lead analytics products",
                job_excerpt="Lead enterprise analytics products across business units.",
                match_level=MatchLevel.UNKNOWN,
                confidence=0.6,
                decision_weight_hint=1.5,
            ),
        ],
        seniority_score=80,
        domain_score=70,
        leadership_score=80,
        methods_score=70,
        outcomes_score=60,
        confidence=0.7,
    )

    analysis = _validate_analysis(_opening(), CanonicalCareerProfile(version=1), "test", response)

    assert analysis.contract_version == "job-fit-analysis-v7"
    assert analysis.qualifications[0].decision_weight == 1.45
    assert analysis.qualifications[1].duplicate_of == analysis.qualifications[0].id
    assert any("near-duplicate" in note for note in analysis.review_notes)


def test_v6_serialized_payload_loads_with_neutral_importance_defaults() -> None:
    payload = {
        "id": "legacy-analysis",
        "job_id": "job",
        "profile_version": 1,
        "contract_version": "job-fit-analysis-v6",
        "model": "legacy",
        "qualifications": [
            {
                "id": "legacy-qualification",
                "importance": "required",
                "requirement": "Own product strategy",
                "job_excerpt": "Own product strategy",
                "match_level": "partial",
                "confidence": 0.8,
            }
        ],
    }

    analysis = JobFitAnalysis.model_validate(payload)

    assert analysis.qualifications[0].decision_weight == 1.0
    assert analysis.qualifications[0].decision_weight_rationale == []
    assert analysis.qualifications[0].duplicate_of is None
