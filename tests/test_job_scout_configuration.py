from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from nerve_center.config import Settings
from nerve_center.discovery.service import DiscoveryService
from nerve_center.persistence.database import Database
from nerve_center.persistence.discovery import (
    CompanyRepository,
    DiscoverySourceRepository,
    JobOpeningRepository,
)
from nerve_center.plugins.job_scout.configuration import (
    register_job_scout_configuration_routes,
)
from nerve_center.plugins.job_scout.settings import JobScoutConfiguration


def _application(tmp_path: Path) -> FastAPI:
    settings = Settings(data_dir=tmp_path / "runtime")
    database = Database(settings)
    database.initialize()
    companies = CompanyRepository(database)
    sources = DiscoverySourceRepository(database)
    jobs = JobOpeningRepository(database)
    discovery = DiscoveryService(companies, sources, jobs)
    application = FastAPI()
    register_job_scout_configuration_routes(
        application,
        database,
        settings,
        None,
        discovery,
        companies,
        sources,
        jobs,
    )
    return application


def test_job_scout_workspace_loads_resume_discovers_keywords_and_registers_sources(
    tmp_path: Path,
) -> None:
    application = _application(tmp_path)
    resume = tmp_path / "resume.txt"
    resume.write_text(
        "Product analytics and product strategy.\n"
        "Led product platform delivery and product roadmap planning.\n",
        encoding="utf-8",
    )
    configuration = JobScoutConfiguration(
        target_titles=["Principal Product Manager"],
        locations=["Remote"],
        remote_preference="remote",
        source_urls=["https://boards.greenhouse.io/acme"],
    )

    with TestClient(application) as client:
        workspace = client.put(
            "/api/v1/modules/job_scout/config",
            json=configuration.model_dump(mode="json"),
        ).json()
        assert workspace["sources"][0]["kind"] == "greenhouse"

        workspace = client.post(
            "/api/v1/modules/job_scout/resume",
            json={"path": str(resume), "analyze_resume": False},
        ).json()
        assert workspace["configuration"]["resume_file_name"] == "resume.txt"
        assert "Principal Product Manager" in workspace["keywords"]["keywords"]
        assert "product" in workspace["keywords"]["keywords"]
        assert workspace["keywords"]["search_queries"]

        cleared = JobScoutConfiguration.model_validate(workspace["configuration"]).model_copy(
            update={"source_urls": [], "source_ids": []}
        )
        client.put(
            "/api/v1/modules/job_scout/config",
            json=cleared.model_dump(mode="json"),
        )
        summary = client.post(
            "/api/v1/modules/job_scout/scan",
            json={"discover_sources": False},
        ).json()

    assert summary["sources_scanned"] == 0
    assert summary["openings_found"] == 0
