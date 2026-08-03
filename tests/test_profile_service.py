import asyncio
from pathlib import Path

from pydantic import BaseModel

from nerve_center.profile.documents import import_source_document
from nerve_center.profile.models import (
    CanonicalCareerProfile,
    CareerExtractionResponse,
    ClaimCategory,
    ClaimDecision,
    ExtractedClaim,
    ExtractedEvidence,
    ExtractedPositioningHypothesis,
    HypothesisDecision,
)
from nerve_center.profile.service import CareerProfileService
from nerve_center.providers.base import (
    ProviderCallMetadata,
    StructuredGenerationResult,
)


class MemoryStore:
    def __init__(self) -> None:
        self.profile = CanonicalCareerProfile()

    def get_profile(self) -> CanonicalCareerProfile:
        return self.profile

    def save_profile(self, profile: CanonicalCareerProfile) -> CanonicalCareerProfile:
        self.profile = profile
        return profile


class FakeProvider:
    name = "fake"

    def __init__(self, response: CareerExtractionResponse) -> None:
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
                id="call-1",
                provider="fake",
                model=model,
                contract_version=contract_version,
                response_schema="CareerExtractionResponse",
                duration_ms=1,
                status="succeeded",
            ),
        )


def test_builds_evidence_backed_profile_and_remembers_hypothesis_decision(tmp_path: Path) -> None:
    source = tmp_path / "resume.txt"
    source.write_text(
        "Product leader\nReduced delivery cycle time by 80 percent.\n",
        encoding="utf-8",
    )
    document = import_source_document(source)
    response = CareerExtractionResponse(
        claims=[
            ExtractedClaim(
                category=ClaimCategory.OUTCOME,
                label="Delivery cycle reduction",
                statement="Reduced delivery cycle time by 80 percent.",
                confidence=0.98,
                evidence=[
                    ExtractedEvidence(
                        locator="line:2",
                        excerpt="Reduced delivery cycle time by 80 percent.",
                    )
                ],
            )
        ],
        positioning_hypotheses=[
            ExtractedPositioningHypothesis(
                label="Operational product leader",
                summary="Leads measurable workflow improvement.",
                suggested_headline="Product Leader, Workflow and Analytics",
                supporting_claim_labels=["Delivery cycle reduction"],
                confidence=0.9,
            )
        ],
    )
    store = MemoryStore()
    service = CareerProfileService(store, FakeProvider(response))

    profile = asyncio.run(service.extract_document(document, model="fake-model"))
    hypothesis = profile.hypotheses[0]
    updated = service.decide_hypothesis(hypothesis.id, HypothesisDecision.APPROVED)
    decided = service.decide_claim(profile.claims[0].id, ClaimDecision.CONFIRMED)
    service.provider.response = response.model_copy(
        update={
            "positioning_hypotheses": [
                response.positioning_hypotheses[0].model_copy(
                    update={"label": "Operational analytics product leadership"}
                )
            ]
        }
    )
    service.decide_hypothesis(hypothesis.id, HypothesisDecision.DISAPPROVED)
    rerun = asyncio.run(service.extract_document(document, model="fake-model"))

    assert profile.claims[0].evidence[0].document_id == document.id
    assert updated.hypotheses[0].decision is HypothesisDecision.APPROVED
    assert decided.claims[0].decision is ClaimDecision.CONFIRMED
    assert rerun.hypotheses[0].decision is HypothesisDecision.DISAPPROVED
    assert rerun.hypotheses[0].id == hypothesis.id


def test_rejects_claim_without_exact_source_evidence(tmp_path: Path) -> None:
    source = tmp_path / "resume.txt"
    source.write_text("Managed a product team.\n", encoding="utf-8")
    document = import_source_document(source)
    response = CareerExtractionResponse(
        claims=[
            ExtractedClaim(
                category=ClaimCategory.LEADERSHIP_SCOPE,
                label="Large team leadership",
                statement="Managed 100 engineers.",
                confidence=0.9,
                evidence=[ExtractedEvidence(locator="line:1", excerpt="Managed 100 engineers")],
            )
        ],
        positioning_hypotheses=[],
    )
    store = MemoryStore()
    profile = asyncio.run(
        CareerProfileService(store, FakeProvider(response)).extract_document(
            document,
            model="fake-model",
        )
    )

    assert profile.claims == []
    assert profile.review_items[0].code == "invalid_evidence"


def test_rejected_claim_cannot_regenerate_positioning_hypothesis(tmp_path: Path) -> None:
    source = tmp_path / "resume.txt"
    source.write_text("Built product analytics.\n", encoding="utf-8")
    document = import_source_document(source)
    response = CareerExtractionResponse(
        claims=[
            ExtractedClaim(
                category=ClaimCategory.CAPABILITY,
                label="Product analytics",
                statement="Built product analytics.",
                confidence=0.9,
                evidence=[
                    ExtractedEvidence(locator="line:1", excerpt="Built product analytics.")
                ],
            )
        ],
        positioning_hypotheses=[
            ExtractedPositioningHypothesis(
                label="Analytics product leader",
                summary="Leads analytics products.",
                suggested_headline="Analytics Product Leader",
                supporting_claim_labels=["Product analytics"],
                confidence=0.9,
            )
        ],
    )
    store = MemoryStore()
    service = CareerProfileService(store, FakeProvider(response))
    profile = asyncio.run(service.extract_document(document, model="fake-model"))

    rejected = service.decide_claim(profile.claims[0].id, ClaimDecision.REJECTED)
    rerun = asyncio.run(service.extract_document(document, model="fake-model"))

    assert rejected.hypotheses == []
    assert rerun.hypotheses == []
