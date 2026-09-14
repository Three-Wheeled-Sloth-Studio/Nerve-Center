from nerve_center.discovery.search import SearchResult, UrlClassification
from nerve_center.plugins.job_scout.attachment_discovery import (
    _prioritize_civic_reference_results,
    _reference_intent_rank,
)


def _result(title: str, url: str, *, snippet: str = "") -> SearchResult:
    return SearchResult(
        title=title,
        url=url,
        snippet=snippet,
        classification=UrlClassification.OTHER,
    )


def test_major_employer_reference_outranks_generic_government_pages() -> None:
    generic_policy = _result(
        "Economic Development Incentive Policy",
        "https://city.example.gov/economic-development/incentives",
    )
    generic_budget = _result(
        "Economic Development FY2027 Budget",
        "https://county.example.gov/files/economic-development-budget.pdf",
    )
    employer_page = _result(
        "Major Employers - Regional Economic Development",
        "https://regionalpartnership.example.org/major-employers",
    )

    visible, evidence = _prioritize_civic_reference_results(
        [generic_policy, generic_budget, employer_page],
        reference_limit=2,
    )

    assert employer_page in visible[:2]
    assert generic_policy in visible[:2]
    assert generic_budget not in visible
    selected = {item["url"] for item in evidence if item["selected"]}
    assert employer_page.url in selected
    assert len(selected) == 2


def test_supported_employer_document_outranks_generic_civic_page() -> None:
    generic_page = _result(
        "Economic Development Overview",
        "https://region.example.gov/economic-development",
    )
    employer_pdf = _result(
        "2027 Employer Survey",
        "https://workforce.example.org/files/employer-survey.pdf",
    )

    assert _reference_intent_rank(employer_pdf) < _reference_intent_rank(generic_page)


def test_reference_preselection_preserves_non_civic_results_and_raw_order() -> None:
    career = SearchResult(
        title="Product careers",
        url="https://company.example/careers",
        classification=UrlClassification.COMPANY_CAREER,
    )
    employer_page = _result(
        "Top Employers",
        "https://partnership.example.org/top-employers",
    )
    generic = _result(
        "Community profile",
        "https://town.example.gov/community-profile",
    )

    visible, _evidence = _prioritize_civic_reference_results(
        [career, generic, employer_page],
        reference_limit=1,
    )

    assert visible[0] == employer_page
    assert visible[1:] == [career]
