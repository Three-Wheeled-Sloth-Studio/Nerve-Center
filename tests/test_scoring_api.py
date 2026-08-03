from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from nerve_center.config import Settings
from nerve_center.discovery.models import (
    AcquisitionClass,
    Company,
    DiscoverySource,
    JobProvenance,
    NormalizedJobOpening,
    SourceKind,
    WorkArrangement,
)
from nerve_center.persistence.database import Database
from nerve_center.persistence.discovery import (
    CompanyRepository,
    DiscoverySourceRepository,
    JobOpeningRepository,
)
from nerve_center.persistence.profile import CareerProfileRepository
from nerve_center.persistence.scoring import FitAnalysisRepository
from nerve_center.profile.models import CanonicalCareerProfile
from nerve_center.providers.base import ProviderModel
from nerve_center.scoring.api import register_scoring_routes
from nerve_center.scoring.models import (
    JobFitAnalysis,
    MatchLevel,
    QualificationAssessment,
    QualificationImportance,
)


class FakeProvider:
    name = "fake"

    async def list_models(self) -> list[ProviderModel]:
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
        raise AssertionError("This API test uses a persisted fit analysis.")


def test_scoring_api_preserves_history_across_settings_versions(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path / "runtime")
    database = Database(settings)
    database.initialize()
    company = Company(id="company-1", canonical_name="Example", domain="example.com")
    source = DiscoverySource(
        id="source-1",
        company_id=company.id,
        name="Manual source",
        kind=SourceKind.MANUAL,
        acquisition_class=AcquisitionClass.MANUAL_IMPORT_ONLY,
        base_url="https://example.com/jobs",
        parser_version="manual-v1",
    )
    opening = NormalizedJobOpening(
        id="job-1",
        company_id=company.id,
        company_name=company.canonical_name,
        company_domain=company.domain,
        title="Product Manager",
        description="Lead product analytics and workflow automation. " * 15,
        location_text="Greensboro, NC",
        work_arrangement=WorkArrangement.HYBRID,
        source_url="https://example.com/jobs/1",
        canonical_url="https://example.com/jobs/1",
        provenance=[
            JobProvenance(
                source_id=source.id,
                connector="manual",
                parser_version="manual-v1",
                source_url="https://example.com/jobs/1",
                direct_employer_source=True,
            )
        ],
    )
    CompanyRepository(database).upsert(company)
    DiscoverySourceRepository(database).upsert(source)
    JobOpeningRepository(database).upsert(opening)
    CareerProfileRepository(database).save_profile(CanonicalCareerProfile(version=1))
    analysis = JobFitAnalysis(
        id="analysis-1",
        job_id=opening.id,
        profile_version=1,
        contract_version="job-fit-analysis-v1",
        model="fake",
        qualifications=[
            QualificationAssessment(
                id="qualification-1",
                importance=QualificationImportance.REQUIRED,
                requirement="Lead product analytics",
                job_excerpt="Lead product analytics",
                match_level=MatchLevel.FULL,
                confidence=0.9,
            )
        ],
        seniority_score=85,
        domain_score=90,
        leadership_score=85,
        methods_score=80,
        outcomes_score=80,
        confidence=0.9,
    )
    FitAnalysisRepository(database).save(analysis)
    application = FastAPI()
    register_scoring_routes(application, database, settings, FakeProvider())

    with TestClient(application) as client:
        client.put(
            "/api/v1/scoring/location-preferences",
            json={
                "id": "canonical",
                "version": 0,
                "home_region": "NC",
                "local_max_commute_minutes": 90,
            },
        )
        client.put(
            f"/api/v1/scoring/jobs/{opening.id}/enrichment",
            json={"job_id": opening.id, "commute_minutes": 25},
        )
        first = client.post(
            f"/api/v1/scoring/jobs/{opening.id}/scores",
            json={"fit_analysis_id": analysis.id},
        )
        current = client.get("/api/v1/scoring/settings").json()
        current["weights"] = {
            "fit": 1,
            "response_likelihood": 0,
            "opportunity_value": 0,
        }
        saved = client.put("/api/v1/scoring/settings", json=current)
        second = client.post(
            f"/api/v1/scoring/jobs/{opening.id}/scores",
            json={"fit_analysis_id": analysis.id},
        )
        history = client.get(f"/api/v1/scoring/jobs/{opening.id}/scores")
        missing = client.get("/api/v1/scoring/jobs/missing/enrichment")

    assert first.status_code == 200
    assert saved.json()["version"] == 2
    assert second.status_code == 200
    assert {item["settings_version"] for item in history.json()} == {1, 2}
    assert missing.status_code == 404
