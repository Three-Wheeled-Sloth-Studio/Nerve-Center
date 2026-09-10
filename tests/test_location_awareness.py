from nerve_center.discovery.models import JobProvenance, NormalizedJobOpening, WorkArrangement
from nerve_center.scoring.location import (
    classify_listing_locations,
    is_specific_physical_location,
    opening_matches_market,
)
from nerve_center.scoring.models import LocationPreferences, LocationScope


def _opening(
    location: str,
    arrangement: WorkArrangement = WorkArrangement.UNKNOWN,
) -> NormalizedJobOpening:
    return NormalizedJobOpening(
        id="job-1",
        company_id="company-1",
        company_name="Example Co",
        company_domain="example.com",
        title="Product Manager",
        description="Own the product.",
        location_text=location,
        work_arrangement=arrangement,
        source_url="https://example.com/jobs/1",
        canonical_url="https://example.com/jobs/1",
        provenance=[
            JobProvenance(
                source_id="source-1",
                connector="fixture",
                parser_version="v1",
                source_url="https://example.com/jobs/1",
                direct_employer_source=True,
            )
        ],
    )


def test_real_location_strings_do_not_trigger_state_substring_false_positives() -> None:
    preferences = LocationPreferences(local_markets=["Greensboro, NC"])

    remote_us = classify_listing_locations(
        ["Remote - US"], preferences, work_arrangement=WorkArrangement.REMOTE
    )
    mixed_remote = classify_listing_locations(
        ["Remote, Canada; Remote, US"],
        preferences,
        work_arrangement=WorkArrangement.REMOTE,
    )
    london_dublin = classify_listing_locations(["London OR Dublin"], preferences)
    montreal = classify_listing_locations(["Montreal, Canada"], preferences)

    assert remote_us[0] is LocationScope.DISTANT
    assert mixed_remote[0] is LocationScope.DISTANT
    assert london_dublin[0] is LocationScope.DISTANT
    assert montreal[0] is LocationScope.DISTANT
    assert not opening_matches_market(_opening("London OR Dublin"), "Portland, OR")
    assert not opening_matches_market(
        _opening("Remote, Canada; Remote, US", WorkArrangement.REMOTE),
        "Greensboro, NC",
    )


def test_state_only_location_is_regional_without_inventing_city_match() -> None:
    preferences = LocationPreferences(local_markets=["Greensboro, NC"])

    state_only = classify_listing_locations(
        ["North Carolina, United States"],
        preferences,
    )
    remote_state = classify_listing_locations(
        ["Remote - North Carolina"],
        preferences,
        work_arrangement=WorkArrangement.REMOTE,
    )

    assert state_only[0] is LocationScope.REGIONAL
    assert remote_state[0] is LocationScope.REGIONAL
    assert not opening_matches_market(
        _opening("North Carolina, United States"),
        "Greensboro, NC",
    )
    assert not opening_matches_market(
        _opening("Remote - North Carolina", WorkArrangement.REMOTE),
        "Greensboro, NC",
    )


def test_market_matching_requires_real_city_or_region_evidence() -> None:
    assert opening_matches_market(_opening("Greensboro, NC"), "Greensboro, NC")
    assert not opening_matches_market(_opening("Minneapolis, MN"), "Greensboro, NC")
    assert not opening_matches_market(
        _opening("Remote - US", WorkArrangement.REMOTE),
        "Greensboro, NC",
    )


def test_remote_and_multi_location_labels_are_not_company_office_evidence() -> None:
    assert is_specific_physical_location("Greensboro, NC")
    assert not is_specific_physical_location("Remote")
    assert not is_specific_physical_location("Remote - US")
    assert not is_specific_physical_location("Remote, Canada; Remote, US")
    assert not is_specific_physical_location("London OR Dublin")
