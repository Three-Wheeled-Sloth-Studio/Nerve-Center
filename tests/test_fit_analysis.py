import asyncio

from pydantic import BaseModel

from nerve_center.discovery.models import JobProvenance, NormalizedJobOpening
from nerve_center.profile.models import (
    CanonicalCareerProfile,
    CareerClaim,
    ClaimCategory,
    EvidenceOrigin,
    EvidenceReference,
)
from nerve_center.providers.base import ProviderCallMetadata, StructuredGenerationResult
from nerve_center.scoring.fit import JobFitAnalyzer
from nerve_center.scoring.models import (
    ExtractedQualificationAssessment,
    FitAnalysisResponse,
    GateCategory,
    MatchLevel,
    QualificationImportance,
)


class FakeProvider:
    name = "fake"

    def __init__(self, response: FitAnalysisResponse) -> None:
        self.response = response

    async def list_models(self):  # type: ignore[no-untyped-def]
        return []

    async def generate_structured(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        response_type: type[BaseModel],
        contract_version: str,
    ):
        del system_prompt, user_prompt, response_type
        return StructuredGenerationResult(
            value=self.response,
            metadata=ProviderCallMetadata(
                id="call-fit",
                provider="fake",
                model=model,
                contract_version=contract_version,
                response_schema="FitAnalysisResponse",
                duration_ms=1,
                status="succeeded",
            ),
        )


def test_fit_analysis_rejects_invalid_evidence_and_unknown_claims() -> None:
    opening = NormalizedJobOpening(
        id="job-1",
        company_id="company-1",
        company_name="Example",
        company_domain="example.com",
        title="Product Director",
        description="Lead enterprise analytics products. Active Secret clearance required.",
        source_url="https://example.com/job",
        canonical_url="https://example.com/job",
        provenance=[
            JobProvenance(
                source_id="source-1",
                connector="json_ld",
                parser_version="v1",
                source_url="https://example.com/job",
                direct_employer_source=True,
            )
        ],
    )
    profile = CanonicalCareerProfile(
        version=3,
        claims=[
            CareerClaim(
                id="claim-1",
                category=ClaimCategory.CAPABILITY,
                label="Enterprise analytics",
                statement="Led enterprise analytics products.",
                confidence=1,
                evidence=[
                    EvidenceReference(
                        origin=EvidenceOrigin.USER_CONFIRMED,
                        locator="user_override",
                        excerpt="Led enterprise analytics products.",
                    )
                ],
            )
        ],
    )
    response = FitAnalysisResponse(
        qualifications=[
            ExtractedQualificationAssessment(
                importance=QualificationImportance.REQUIRED,
                requirement="Lead analytics products",
                job_excerpt="Lead enterprise analytics products.",
                matched_claim_ids=["claim-1"],
                match_level=MatchLevel.FULL,
                confidence=0.95,
            ),
            ExtractedQualificationAssessment(
                importance=QualificationImportance.REQUIRED,
                requirement="AWS certification",
                job_excerpt="AWS certification required.",
                matched_claim_ids=["missing-claim"],
                match_level=MatchLevel.FULL,
                confidence=0.9,
                gate_category=GateCategory.LICENSE,
            ),
        ],
        seniority_score=90,
        domain_score=95,
        leadership_score=90,
        methods_score=80,
        outcomes_score=75,
        confidence=0.9,
    )

    analysis = asyncio.run(
        JobFitAnalyzer(FakeProvider(response)).analyze(opening, profile, model="fake")
    )

    assert analysis.qualifications[0].match_level is MatchLevel.FULL
    assert analysis.qualifications[0].matched_claim_ids == ["claim-1"]
    assert analysis.qualifications[1].match_level is MatchLevel.UNKNOWN
    assert analysis.qualifications[1].matched_claim_ids == []
    assert analysis.review_notes
