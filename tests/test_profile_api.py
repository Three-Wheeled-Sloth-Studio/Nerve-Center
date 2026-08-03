from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from nerve_center.api.schemas import (
    ClaimOverrideRequest,
    DocumentRegisterRequest,
    HypothesisDecisionRequest,
    ProfileExtractRequest,
)
from nerve_center.config import Settings
from nerve_center.persistence.database import Database
from nerve_center.profile.api import register_profile_routes
from nerve_center.profile.models import (
    CareerExtractionResponse,
    ClaimCategory,
    ExtractedClaim,
    ExtractedEvidence,
    ExtractedPositioningHypothesis,
)
from nerve_center.providers.base import (
    ProviderCallMetadata,
    ProviderModel,
    StructuredGenerationResult,
)


class FakeProvider:
    name = "fake"

    async def list_models(self) -> list[ProviderModel]:
        return [ProviderModel(id="fake:1", label="fake:1")]

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
        value = CareerExtractionResponse(
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
        return StructuredGenerationResult(
            value=value,
            metadata=ProviderCallMetadata(
                id="call-api",
                provider="fake",
                model=model,
                contract_version=contract_version,
                response_schema="CareerExtractionResponse",
                duration_ms=1,
                status="succeeded",
            ),
        )


def test_profile_routes_cover_import_extract_decide_and_override(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path / "runtime")
    database = Database(settings)
    database.initialize()
    application = FastAPI()
    register_profile_routes(application, database, settings, FakeProvider())
    source = tmp_path / "resume.txt"
    source.write_text("Built product analytics.\n", encoding="utf-8")

    with TestClient(application) as client:
        assert client.get("/api/v1/providers/ollama/models").json()[0]["id"] == "fake:1"
        document = client.post(
            "/api/v1/profile/documents",
            json=DocumentRegisterRequest(path=str(source)).model_dump(mode="json"),
        ).json()
        profile = client.post(
            "/api/v1/profile/extract",
            json=ProfileExtractRequest(
                document_id=document["id"],
                model="fake:1",
            ).model_dump(mode="json"),
        ).json()
        hypothesis = profile["hypotheses"][0]
        profile = client.post(
            f"/api/v1/profile/hypotheses/{hypothesis['id']}/decision",
            json=HypothesisDecisionRequest(decision="approved").model_dump(mode="json"),
        ).json()
        claim = profile["claims"][0]
        profile = client.put(
            f"/api/v1/profile/claims/{claim['id']}",
            json=ClaimOverrideRequest(
                label="Product analytics leadership",
                statement="Built and led product analytics.",
            ).model_dump(mode="json"),
        ).json()

    assert profile["hypotheses"][0]["decision"] == "approved"
    assert profile["claims"][0]["decision"] == "confirmed"
    assert profile["claims"][0]["evidence"][0]["origin"] == "user_confirmed"
