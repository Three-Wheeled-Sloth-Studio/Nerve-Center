from pathlib import Path

from nerve_center.config import Settings
from nerve_center.discovery.models import (
    AcquisitionClass,
    Company,
    DiscoverySource,
    JobProvenance,
    NormalizedJobOpening,
    SourceKind,
)
from nerve_center.persistence.database import Database
from nerve_center.persistence.discovery import (
    CompanyRepository,
    DiscoverySourceRepository,
    JobOpeningRepository,
)
from nerve_center.plugins.job_scout.discovery_quality import DiscoveryQualityRepository


def test_opening_overlap_is_derived_from_durable_source_provenance(tmp_path: Path) -> None:
    database = Database(Settings(data_dir=tmp_path / "runtime"))
    database.initialize()
    companies = CompanyRepository(database)
    sources = DiscoverySourceRepository(database)
    jobs = JobOpeningRepository(database)
    learning = DiscoveryQualityRepository(database)

    first = learning.ensure_strategy(
        {
            "kind": "public_search",
            "hypothesis_family": "direct_role",
            "anchor": "Product Manager",
        },
        origin="test",
    )
    second = learning.ensure_strategy(
        {
            "kind": "public_search",
            "hypothesis_family": "domain_capability",
            "anchor": "health analytics",
        },
        origin="test",
    )
    company = companies.upsert(
        Company(id="company-1", canonical_name="Example Co", domain="example.com")
    )
    source = sources.upsert(
        DiscoverySource(
            id="source-1",
            company_id=company.id,
            name="Example careers",
            kind=SourceKind.JSON_LD,
            acquisition_class=AcquisitionClass.PUBLIC_HTML_ALLOWED,
            base_url="https://example.com/careers",
            configuration={"discovery_strategy_ids": [first.id, second.id]},
            parser_version="jsonld-v1",
        )
    )
    jobs.upsert(
        NormalizedJobOpening(
            id="job-1",
            company_id=company.id,
            company_name=company.canonical_name,
            company_domain=company.domain,
            title="Product Manager",
            description="Own a healthcare analytics product.",
            source_url="https://example.com/jobs/1",
            canonical_url="https://example.com/jobs/1",
            provenance=[
                JobProvenance(
                    source_id=source.id,
                    connector="json_ld",
                    parser_version="jsonld-v1",
                    source_url="https://example.com/jobs/1",
                    direct_employer_source=True,
                )
            ],
        )
    )

    rows = {item["id"]: item for item in learning.discovery_audit()["strategies"]}

    assert rows[first.id]["overlap_opening_count"] == 1
    assert rows[first.id]["overlap_opening_ids"] == ["job-1"]
    assert rows[second.id]["overlap_opening_count"] == 1
