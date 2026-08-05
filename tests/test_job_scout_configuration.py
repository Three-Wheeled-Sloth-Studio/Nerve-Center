import base64
import json
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
from nerve_center.plugins.job_scout.bootstrap import install_job_scout
from nerve_center.plugins.job_scout.settings import (
    JobScoutConfiguration,
    JobScoutConfigurationStore,
)


def _application(tmp_path: Path) -> FastAPI:
    settings = Settings(data_dir=tmp_path / "runtime")
    database = Database(settings)
    database.initialize()
    companies = CompanyRepository(database)
    sources = DiscoverySourceRepository(database)
    jobs = JobOpeningRepository(database)
    discovery = DiscoveryService(companies, sources, jobs)
    application = FastAPI()
    # Use the normal module composition path so the upload and configuration
    # contracts are exercised together.
    install_job_scout(application, database, settings, None)
    return application


def test_job_scout_workspace_uploads_resume_preserves_values_and_filters_keywords(
    tmp_path: Path,
) -> None:
    application = _application(tmp_path)
    resume = (
        "Paragraph across product analytics and product strategy.\r\n"
        "Led product platform delivery and product roadmap planning.\r\n"
    ).encode()
    configuration = JobScoutConfiguration(
        target_titles=["Principal Product Manager"],
        locations=["Raleigh, NC"],
        remote_preference="hybrid",
        source_urls=["https://boards.greenhouse.io/acme"],
        manual_keywords=["product operations"],
    )

    with TestClient(application) as client:
        workspace = client.put(
            "/api/v1/modules/job_scout/config",
            json=configuration.model_dump(mode="json"),
        ).json()
        assert workspace["configuration"]["target_titles"] == ["Principal Product Manager"]
        assert workspace["configuration"]["locations"] == ["Raleigh, NC"]
        assert workspace["configuration"]["manual_keywords"] == ["product operations"]
        assert workspace["sources"][0]["kind"] == "greenhouse"

        response = client.post(
            "/api/v1/modules/job_scout/resume/upload",
            json={
                "file_name": "Joe Wheeler Resume.txt",
                "content_base64": base64.b64encode(resume).decode("ascii"),
                "analyze_resume": False,
            },
        )
        assert response.status_code == 201
        workspace = response.json()
        assert workspace["configuration"]["resume_file_name"] == "Joe Wheeler Resume.txt"
        assert "Principal Product Manager" in workspace["keywords"]["keywords"]
        assert "product operations" in workspace["keywords"]["keywords"]
        assert "product analytics" in workspace["keywords"]["keywords"]
        assert "product strategy" in workspace["keywords"]["keywords"]
        assert "product" in workspace["keywords"]["keywords"]
        assert "paragraph" not in workspace["keywords"]["keywords"]
        assert "across" not in workspace["keywords"]["keywords"]
        assert workspace["keywords"]["search_queries"]

        stored_path = Path(workspace["documents"][0]["source_path"])
        assert stored_path.name == "Joe Wheeler Resume.txt"
        assert stored_path.is_file()
        assert tmp_path / "runtime" / "modules" / "job_scout" / "imports" in stored_path.parents

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


def test_legacy_generated_keywords_are_not_migrated_as_manual_input(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path / "runtime")
    store = JobScoutConfigurationStore(settings)
    store.path.parent.mkdir(parents=True, exist_ok=True)
    store.path.write_text(
        json.dumps(
            {
                "target_titles": ["Product Director"],
                "locations": [],
                "remote_preference": "any",
                "source_urls": [],
                "source_ids": [],
                "allowed_domains": [],
                "disallowed_domains": [],
                "keywords": ["paragraph", "across", "product"],
                "broad_search_enabled": False,
                "scan_interval_minutes": 1440,
            }
        ),
        encoding="utf-8",
    )

    configuration = store.load()
    assert configuration.manual_keywords == []
    assert configuration.keywords == ["paragraph", "across", "product"]
    store.save(configuration)

    persisted = json.loads(store.path.read_text(encoding="utf-8"))
    assert "keywords" not in persisted
    assert persisted["manual_keywords"] == []
