from nerve_center.discovery.models import JobProvenance, NormalizedJobOpening
from nerve_center.scoring.models import CompanyEnrichment, LocationPreferences
from nerve_center.scoring.service import (
    _effective_location_preferences,
    _merge_observed_company_presence,
    _title_role_alignment,
)


def _opening(
    *,
    job_id: str,
    location: str,
    direct_employer_source: bool,
) -> NormalizedJobOpening:
    url = f"https://example.com/jobs/{job_id}"
    return NormalizedJobOpening(
        id=job_id,
        company_id="company-1",
        company_name="Example Co",
        company_domain="example.com",
        title="Product Director",
        description="Lead the product organization.",
        location_text=location,
        source_url=url,
        canonical_url=url,
        parser_confidence=0.9,
        provenance=[
            JobProvenance(
                source_id=f"source-{job_id}",
                connector="test",
                parser_version="v1",
                source_url=url,
                direct_employer_source=direct_employer_source,
            )
        ],
    )


def test_title_role_alignment_separates_target_and_unrelated_roles() -> None:
    targets = ["Director of Product Management", "Head of Product"]

    assert _title_role_alignment("Senior Director, Product Management", targets) == 1.0
    assert _title_role_alignment("Principal Product Manager", targets) == 1.0
    assert _title_role_alignment("Director, Product Marketing", targets) == 0.5
    assert _title_role_alignment("Senior Software Engineer", targets) == 0.0
    assert _title_role_alignment("Accounting Manager", targets) == 0.0


def test_configured_job_scout_markets_feed_location_preferences() -> None:
    preferences = _effective_location_preferences(
        LocationPreferences(),
        ["Greensboro, NC", "Winston-Salem, NC"],
    )

    assert preferences.home_label == "Greensboro, NC"
    assert preferences.local_markets == ["Greensboro, NC", "Winston-Salem, NC"]
    assert preferences.home_region == "NC"
    assert preferences.regional_regions == ["NC"]


def test_direct_employer_location_evidence_builds_company_presence() -> None:
    enrichment = _merge_observed_company_presence(
        CompanyEnrichment(company_id="company-1"),
        [
            _opening(
                job_id="local",
                location="Greensboro, NC",
                direct_employer_source=True,
            ),
            _opening(
                job_id="remote",
                location="Remote",
                direct_employer_source=True,
            ),
            _opening(
                job_id="aggregator",
                location="Winston-Salem, NC",
                direct_employer_source=False,
            ),
        ],
    )

    assert [item.label for item in enrichment.offices] == ["Greensboro, NC"]
    assert enrichment.offices[0].region == "NC"
    assert enrichment.offices[0].evidence_url == "https://example.com/jobs/local"
