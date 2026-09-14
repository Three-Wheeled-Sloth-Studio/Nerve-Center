import asyncio

from nerve_center.discovery.search import SearchResult, UrlClassification
from nerve_center.plugins.job_scout.attachment_discovery import (
    _IntentAwareReferenceAdapter,
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


def test_civic_self_employment_page_is_not_a_landscape_reference() -> None:
    hr_page = _result(
        "Employment Opportunities",
        "https://town.example.gov/human-resources/jobs",
    )
    employer_page = _result(
        "Largest Employers",
        "https://town.example.gov/business/largest-employers",
    )

    visible, evidence = _prioritize_civic_reference_results(
        [hr_page, employer_page],
        reference_limit=6,
    )

    assert visible == [employer_page, hr_page]
    rejected = next(item for item in evidence if item["url"] == hr_page.url)
    assert rejected["eligible"] is False
    assert rejected["rejection_reason"] == "civic_self_employment"


def test_reference_adapter_preserves_ranked_fallback_pool_and_raw_count() -> None:
    results = [
        _result(
            f"Top Employers directory {index}",
            f"https://region.example.org/employers/{index}",
        )
        for index in range(7)
    ]

    class Search:
        async def search_references(self, _query: str) -> list[SearchResult]:
            return results

    adapter = _IntentAwareReferenceAdapter(Search())
    visible = asyncio.run(adapter.search_references("fictional market top employers"))

    assert adapter.raw_result_count == 7
    assert len(visible) == 6
    assert sum(bool(item["selected"]) for item in adapter.selection_evidence) == 6
