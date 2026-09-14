import asyncio
import io
import json
import runpy
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import httpx
import pytest
from pypdf import PdfWriter
from reportlab.pdfgen import canvas

from nerve_center.config import Settings
from nerve_center.discovery.fetching import (
    DomainRequestGate,
    FetchResponse,
    HttpFetcher,
    ResponseTooLargeError,
)
from nerve_center.discovery.models import Company
from nerve_center.discovery.search import ReferenceDocument, SearchChallengeError, SearchResult
from nerve_center.discovery.service import DiscoveryService
from nerve_center.persistence.database import Database
from nerve_center.persistence.discovery import (
    CompanyRepository,
    DiscoverySourceRepository,
    JobOpeningRepository,
    SearchCacheRepository,
)
from nerve_center.plugins.job_scout.attachment_discovery import (
    AttachmentAwareJobScoutDiscoveryLoop,
)
from nerve_center.plugins.job_scout.configuration import JobScoutCoordinator
from nerve_center.plugins.job_scout.discovery_quality import DiscoveryQualityRepository
from nerve_center.plugins.job_scout.market import MarketAlias
from nerve_center.plugins.job_scout.reference_attachments import (
    MAX_ATTACHMENT_CANDIDATES_PER_REFERENCE,
    AttachmentDocumentError,
    DirectoryDocument,
    PublicAttachmentFetcher,
    discover_directory_attachments,
    parse_directory_document,
)
from nerve_center.plugins.job_scout.settings import JobScoutConfiguration


def _pdf_bytes(lines: list[str]) -> bytes:
    buffer = io.BytesIO()
    document = canvas.Canvas(buffer, pagesize=(612, 792))
    y = 750
    for line in lines:
        document.drawString(72, y, line)
        y -= 18
    document.save()
    return buffer.getvalue()


def _xlsx_bytes(rows: list[list[str]]) -> bytes:
    buffer = io.BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        xml_rows = []
        for row_index, row in enumerate(rows, start=1):
            cells = []
            for column_index, value in enumerate(row):
                column = chr(ord("A") + column_index)
                cells.append(
                    f'<c r="{column}{row_index}" t="inlineStr"><is><t>{value}</t></is></c>'
                )
            xml_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                f'<sheetData>{"".join(xml_rows)}</sheetData></worksheet>'
            ),
        )
    return buffer.getvalue()


def _document(
    url: str,
    content: bytes,
    content_type: str,
    *,
    text: str = "",
    cache_status: str = "miss",
) -> DirectoryDocument:
    return DirectoryDocument(
        url=url,
        content=content,
        text=text,
        content_type=content_type,
        cache_status=cache_status,
    )


def test_pdf_employer_section_extracts_only_bounded_directory_names() -> None:
    content = _pdf_bytes(
        [
            "Regional Workforce Brief",
            "Major Employers",
            "Employer Employees",
            "Atlas Lantern Works 1,250",
            "Cedar Signal Labs 875",
            "Contact",
            "Example Regional Council",
        ]
    )

    parsed = parse_directory_document(
        _document("https://civic.example/employers.pdf", content, "application/pdf")
    )

    assert parsed.status == "parsed"
    assert parsed.extraction_method == "pdf_text_employer_section"
    assert parsed.candidates == ("Atlas Lantern Works", "Cedar Signal Labs")
    assert parsed.units_inspected == 1


def test_csv_json_and_xlsx_require_explicit_employer_structure() -> None:
    csv_text = (
        "Employer Name,Employees\n"
        "Northstar Fabrication,700\n"
        "Juniper Transit Systems,540\n"
    )
    csv_parsed = parse_directory_document(
        _document(
            "https://civic.example/employers.csv",
            csv_text.encode(),
            "text/csv",
            text=csv_text,
        )
    )
    assert csv_parsed.candidates == (
        "Northstar Fabrication",
        "Juniper Transit Systems",
    )

    json_text = json.dumps(
        {
            "publisher": {
                "@type": "Organization",
                "name": "Fictional Chamber Alliance",
                "organization_name": "Fictional Chamber Alliance",
            },
            "author": {"organization_name": "Example Regional Partnership"},
            "employers": [
                {"employer_name": "Copper Finch Robotics"},
                {"company_name": "Mosaic Harbor Health"},
            ],
        }
    )
    json_parsed = parse_directory_document(
        _document(
            "https://civic.example/employers.json",
            json_text.encode(),
            "application/json",
            text=json_text,
        )
    )
    assert json_parsed.candidates == (
        "Copper Finch Robotics",
        "Mosaic Harbor Health",
    )
    assert "Fictional Chamber Alliance" not in json_parsed.candidates
    assert "Example Regional Partnership" not in json_parsed.candidates

    xlsx_content = _xlsx_bytes(
        [
            ["Company Name", "Employees"],
            ["Blue Heron Materials", "300"],
            ["Lantern Ridge Software", "220"],
        ]
    )
    xlsx_parsed = parse_directory_document(
        _document(
            "https://civic.example/employers.xlsx",
            xlsx_content,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    )
    assert xlsx_parsed.candidates == (
        "Blue Heron Materials",
        "Lantern Ridge Software",
    )


def test_attachment_link_discovery_retains_parent_url_and_link_text() -> None:
    links = discover_directory_attachments(
        "https://region.example.gov/workforce/overview",
        """
        <h2>Major Employers</h2>
        <a href="/files/employer-directory.pdf" type="application/pdf">2026 employer directory</a>
        <a href="/files/company-list.csv">Download company list</a>
        <a href="/files/businesses.docx">Legacy business directory</a>
        <h2>Contact</h2>
        <a href="/files/board-minutes.pdf">Board minutes</a>
        """,
    )

    assert [item.format_hint for item in links] == ["pdf", "csv", "unsupported"]
    assert links[0].parent_url == "https://region.example.gov/workforce/overview"
    assert links[0].url == "https://region.example.gov/files/employer-directory.pdf"
    assert links[0].link_text == "2026 employer directory"


def test_unsupported_malformed_and_password_protected_documents_fail_safely() -> None:
    unsupported = parse_directory_document(
        _document(
            "https://civic.example/employers.docx",
            b"not-a-document",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    )
    malformed = parse_directory_document(
        _document(
            "https://civic.example/employers.pdf",
            b"%PDF-malformed",
            "application/pdf",
        )
    )
    encrypted_buffer = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.encrypt("secret")
    writer.write(encrypted_buffer)
    protected = parse_directory_document(
        _document(
            "https://civic.example/protected.pdf",
            encrypted_buffer.getvalue(),
            "application/pdf",
        )
    )

    assert unsupported.status == "unsupported"
    assert malformed.status == "invalid"
    assert protected.status == "invalid"
    assert "Password-protected" in protected.detail


def test_candidate_and_row_limits_are_enforced() -> None:
    rows = ["Employer Name,Employees"] + [
        f"Fictional Employer {index},{1000 - index}" for index in range(700)
    ]
    text = "\n".join(rows)
    parsed = parse_directory_document(
        _document(
            "https://civic.example/employers.csv",
            text.encode(),
            "text/csv",
            text=text,
        )
    )

    assert len(parsed.candidates) == MAX_ATTACHMENT_CANDIDATES_PER_REFERENCE
    assert parsed.units_inspected == 500


class _FixtureBinaryFetcher:
    def __init__(self, responses: dict[str, FetchResponse | Exception]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    async def get(self, url: str, **_kwargs):  # type: ignore[no-untyped-def]
        self.calls.append(url)
        response = self.responses[url]
        if isinstance(response, Exception):
            raise response
        return response


def _attachment_cache(tmp_path: Path) -> SearchCacheRepository:
    settings = Settings(data_dir=tmp_path / "cache-runtime")
    database = Database(settings)
    database.initialize()
    return SearchCacheRepository(database)


def test_attachment_cache_reuse_does_not_refetch(tmp_path: Path) -> None:
    url = "https://civic.example/employers.csv"
    body = b"Employer Name\nSilver Kite Logistics\n"
    fetcher = _FixtureBinaryFetcher(
        {
            url: FetchResponse(
                url=url,
                status_code=200,
                text=body.decode(),
                headers={"content-type": "text/csv"},
                challenged=False,
                throttled=False,
                content=body,
            )
        }
    )
    attachments = PublicAttachmentFetcher(
        _attachment_cache(tmp_path),
        fetcher=fetcher,  # type: ignore[arg-type]
    )

    first = asyncio.run(attachments.fetch(url))
    second = asyncio.run(attachments.fetch(url))

    assert first.cache_status == "miss"
    assert second.cache_status == "hit"
    assert fetcher.calls == [url]


def test_challenged_attachment_enters_cooldown_without_repeat_request(tmp_path: Path) -> None:
    url = "https://civic.example/employers.pdf"
    fetcher = _FixtureBinaryFetcher(
        {
            url: FetchResponse(
                url=url,
                status_code=403,
                text="security challenge",
                headers={"content-type": "text/html"},
                challenged=True,
                throttled=False,
                content=b"security challenge",
            )
        }
    )
    attachments = PublicAttachmentFetcher(
        _attachment_cache(tmp_path),
        fetcher=fetcher,  # type: ignore[arg-type]
    )

    with pytest.raises(SearchChallengeError):
        asyncio.run(attachments.fetch(url))
    assert attachments.cache_status(url) == "retry_deferred"
    with pytest.raises(SearchChallengeError):
        asyncio.run(attachments.fetch(url))
    assert fetcher.calls == [url]


def test_oversized_attachment_is_cached_invalid(tmp_path: Path) -> None:
    url = "https://civic.example/huge.pdf"
    fetcher = _FixtureBinaryFetcher(
        {url: ResponseTooLargeError("fixture response too large")}
    )
    attachments = PublicAttachmentFetcher(
        _attachment_cache(tmp_path),
        fetcher=fetcher,  # type: ignore[arg-type]
    )

    with pytest.raises(AttachmentDocumentError):
        asyncio.run(attachments.fetch(url))
    assert attachments.cache_status(url) == "invalid"


def test_http_fetcher_stops_streaming_after_response_limit() -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            200,
            content=b"x" * 100,
            headers={"content-type": "application/pdf"},
        )
    )
    client = httpx.AsyncClient(transport=transport)
    fetcher = HttpFetcher(
        client=client,
        gate=DomainRequestGate(1, minimum_interval_seconds=0),
    )
    try:
        with pytest.raises(ResponseTooLargeError):
            asyncio.run(fetcher.get("https://example.test/file.pdf", max_bytes=10))
    finally:
        asyncio.run(client.aclose())


class _FixtureMarket:
    async def expand(self, locations: list[str], **_kwargs):  # type: ignore[no-untyped-def]
        return [
            MarketAlias(location, "configured", 0.0, "configured_starting_location")
            for location in locations
        ]


class _FixtureSurfaceResolver:
    async def resolve(self, _company: Company) -> list[str]:
        return []


class _AttachmentReferenceSearch:
    def __init__(self, html: str) -> None:
        self.html = html
        self.reference_url = "https://region.example.gov/employers"

    async def search(self, query: str) -> list[SearchResult]:
        return await self.search_references(query)

    async def search_references(self, _query: str) -> list[SearchResult]:
        return [
            SearchResult(
                title="Regional employer directory",
                url=self.reference_url,
            )
        ]

    def reference_cache_status(self, _url: str) -> str:
        return "hit"

    async def fetch_reference(self, url: str) -> ReferenceDocument:
        return ReferenceDocument(
            url=url,
            text=self.html,
            content_type="text/html",
            cache_status="hit",
        )


class _ExtensionlessPdfReferenceSearch(_AttachmentReferenceSearch):
    def __init__(self, content: bytes) -> None:
        super().__init__("")
        self.reference_url = "https://region.example.gov/employer-report"
        self.final_url = "https://region.example.gov/document/view/42"
        self.content = content

    async def search_references(self, _query: str) -> list[SearchResult]:
        return [SearchResult(title="Largest Employers", url=self.reference_url)]

    async def fetch_reference(self, url: str) -> ReferenceDocument:
        assert url == self.reference_url
        return ReferenceDocument(
            url=self.final_url,
            text="",
            content_type="application/pdf",
            cache_status="hit",
            content=self.content,
        )


class _FixtureAttachmentFetcher:
    def __init__(
        self,
        statuses: dict[str, str],
        documents: dict[str, DirectoryDocument],
    ) -> None:
        self.statuses = statuses
        self.documents = documents
        self.calls: list[str] = []
        self.invalid: list[str] = []

    def cache_status(self, url: str) -> str:
        return self.statuses.get(url, "miss")

    async def fetch(self, url: str) -> DirectoryDocument:
        self.calls.append(url)
        return self.documents[url]

    def mark_invalid(self, url: str, _message: str) -> None:
        self.invalid.append(url)
        self.statuses[url] = "invalid"


def _build_attachment_loop(
    tmp_path: Path,
    *,
    search: _AttachmentReferenceSearch,
    attachments: _FixtureAttachmentFetcher,
) -> tuple[
    AttachmentAwareJobScoutDiscoveryLoop,
    DiscoveryQualityRepository,
    CompanyRepository,
]:
    settings = Settings(data_dir=tmp_path / "runtime")
    database = Database(settings)
    database.initialize()
    companies = CompanyRepository(database)
    sources = DiscoverySourceRepository(database)
    jobs = JobOpeningRepository(database)
    discovery = DiscoveryService(companies, sources, jobs)
    coordinator = JobScoutCoordinator(
        settings,
        database,
        None,
        discovery,
        companies,
        sources,
        jobs,
    )
    coordinator.store.save(
        JobScoutConfiguration(
            target_titles=["Product Manager"],
            locations=["Example, NC"],
            public_job_boards=[],
        )
    )
    learning = DiscoveryQualityRepository(database)
    loop = AttachmentAwareJobScoutDiscoveryLoop(
        settings,
        coordinator,
        discovery,
        companies,
        sources,
        jobs,
        learning,
        market=_FixtureMarket(),
        search_adapter=search,  # type: ignore[arg-type]
        surface_resolver=_FixtureSurfaceResolver(),
        attachment_fetcher=attachments,  # type: ignore[arg-type]
        strategies_per_cycle=1,
    )
    return loop, learning, companies


def test_deferred_attachment_skips_to_eligible_and_remains_hypothesis(
    tmp_path: Path,
) -> None:
    deferred = "https://region.example.gov/files/deferred.pdf"
    eligible = "https://region.example.gov/files/employers.csv"
    html = """
        <h2>Major Employers</h2>
        <a href="/files/deferred.pdf">Major employers PDF</a>
        <a href="/files/employers.csv">Employer directory CSV</a>
    """
    search = _AttachmentReferenceSearch(html)
    csv_text = "Employer Name,Employees\nFictional Circuit Works,420\n"
    attachments = _FixtureAttachmentFetcher(
        {deferred: "retry_deferred", eligible: "miss"},
        {
            eligible: _document(
                eligible,
                csv_text.encode(),
                "text/csv",
                text=csv_text,
            )
        },
    )
    loop, learning, companies = _build_attachment_loop(
        tmp_path,
        search=search,
        attachments=attachments,
    )
    asyncio.run(loop.prepare("run-attachments"))
    landscape = learning.ensure_strategy(
        {
            "kind": "public_search",
            "hypothesis_family": "local_employer",
            "anchor": "major employers",
            "location": "Example, NC",
            "source_domain": "web",
        },
        origin="fixture",
    )
    learning.select_strategies = (  # type: ignore[method-assign]
        lambda *_args, **_kwargs: [landscape]
    )

    cycle = asyncio.run(loop.cycle("run-attachments", 1, request_limit=10))

    hypotheses = [
        item
        for item in learning.list_strategies()
        if item.dimensions.get("hypothesis_family") == "local_employer_deepen"
    ]
    assert attachments.calls == [eligible]
    assert cycle.request_count == 2  # one public search plus one eligible attachment fetch
    assert cycle.coverage["attachment_links_discovered"] == 2
    assert cycle.coverage["attachment_fetches_attempted"] == 1
    assert cycle.coverage["attachment_fetches_deferred"] == 1
    assert cycle.coverage["attachment_documents_parsed"] == 1
    assert cycle.coverage["attachment_employer_candidates_extracted"] == 1
    assert cycle.coverage["employer_candidates_discovered"] >= 1
    assert len(companies.list()) == 0
    assert hypotheses[0].dimensions["anchor"] == "Fictional Circuit Works"
    assert hypotheses[0].dimensions["employer_evidence_parent_url"] == search.reference_url
    assert hypotheses[0].dimensions["employer_evidence_url"] == eligible
    assert hypotheses[0].dimensions["employer_evidence_link_text"] == (
        "Employer directory CSV"
    )
    assert hypotheses[0].dimensions["employer_evidence_extraction_method"] == (
        "delimited_employer_field"
    )


def test_extensionless_pdf_reference_reuses_response_in_document_parser(
    tmp_path: Path,
) -> None:
    search = _ExtensionlessPdfReferenceSearch(
        _pdf_bytes(
            [
                "Regional Workforce Brief",
                "Largest Employers",
                "Employer Employees",
                "Fictional Beacon Works 900",
                "Imaginary River Systems 700",
                "Contact",
            ]
        )
    )
    attachments = _FixtureAttachmentFetcher({}, {})
    loop, learning, companies = _build_attachment_loop(
        tmp_path,
        search=search,
        attachments=attachments,
    )
    asyncio.run(loop.prepare("run-extensionless-pdf"))
    landscape = learning.ensure_strategy(
        {
            "kind": "public_search",
            "hypothesis_family": "local_employer",
            "anchor": "major employers",
            "location": "Example, NC",
            "source_domain": "web",
        },
        origin="fixture",
    )

    outcome, requests, _warnings = asyncio.run(
        loop._execute_public_search(landscape)
    )

    stages = outcome.detail["stages"]
    hypotheses = [
        item
        for item in learning.list_strategies()
        if item.dimensions.get("hypothesis_family") == "local_employer_deepen"
    ]
    assert requests == 1
    assert attachments.calls == []
    assert stages["attachment_fetches_attempted"] == 0
    assert stages["attachment_documents_parsed"] == 1
    assert stages["attachment_employer_candidates_extracted"] == 2
    assert len(companies.list()) == 0
    assert {item.dimensions["anchor"] for item in hypotheses} == {
        "Fictional Beacon Works",
        "Imaginary River Systems",
    }
    evidence = stages["attachment_reference_evidence"]
    assert evidence[0]["parent_page_url"] == search.reference_url
    assert evidence[0]["attachment_url"] == search.final_url
    assert evidence[0]["content_type"] == "application/pdf"
    assert evidence[0]["status"] == "parsed"
    reference = stages["employer_reference_evidence"][0]
    assert reference["requested_url"] == search.reference_url
    assert reference["url"] == search.final_url


def test_attachment_request_cap_and_candidate_limit_hold_in_discovery(tmp_path: Path) -> None:
    links = [f"https://region.example.gov/files/employers-{index}.csv" for index in range(4)]
    html = "<h2>Major Employers</h2>" + "".join(
        f'<a href="{url}">Employer directory {index}</a>'
        for index, url in enumerate(links)
    )
    search = _AttachmentReferenceSearch(html)
    documents = {}
    for index, url in enumerate(links):
        text = "Employer Name\n" + "\n".join(
            f"Fictional Works {index}-{candidate}" for candidate in range(10)
        )
        documents[url] = _document(url, text.encode(), "text/csv", text=text)
    attachments = _FixtureAttachmentFetcher(
        {url: "miss" for url in links},
        documents,
    )
    loop, learning, _companies = _build_attachment_loop(
        tmp_path,
        search=search,
        attachments=attachments,
    )
    asyncio.run(loop.prepare("run-caps"))
    landscape = learning.ensure_strategy(
        {
            "kind": "public_search",
            "hypothesis_family": "local_employer",
            "anchor": "major employers",
            "location": "Example, NC",
            "source_domain": "web",
        },
        origin="fixture",
    )

    outcome, requests, _warnings = asyncio.run(
        loop._execute_public_search(landscape)
    )

    stages = outcome.detail["stages"]
    assert requests == 3  # public search plus at most two attachment fetches
    assert len(attachments.calls) == 2
    assert stages["attachment_fetches_attempted"] == 2
    assert stages["attachment_employer_candidates_extracted"] == (
        MAX_ATTACHMENT_CANDIDATES_PER_REFERENCE
    )
    evidence = stages["attachment_reference_evidence"]
    assert evidence[0]["parent_page_url"] == search.reference_url
    assert evidence[0]["attachment_url"] == links[0]


def test_live_report_preserves_attachment_coverage(tmp_path: Path, monkeypatch) -> None:
    script = runpy.run_path(
        str(Path(__file__).parents[1] / "scripts" / "run_job_scout_live.py")
    )
    monitor_session = script["monitor_session"]
    report: dict[str, object] = {}

    def request(_endpoint, path, method="GET", payload=None):  # type: ignore[no-untyped-def]
        if path.startswith("/api/v1/sessions?"):
            return [
                {
                    "id": "session",
                    "status": "running",
                    "module_run_ids": {"job_scout": "run"},
                }
            ]
        if path == "/api/v1/runs/run":
            return {
                "status": "partial",
                "checkpoint": {
                    "terminal_reason": "no_work",
                    "coverage": {
                        "attachment_links_discovered": 4,
                        "attachment_fetches_attempted": 2,
                        "attachment_cache_hits": 1,
                        "attachment_fetches_deferred": 1,
                        "attachment_documents_parsed": 2,
                        "attachment_documents_unsupported_or_invalid": 1,
                        "attachment_employer_candidates_extracted": 3,
                    },
                },
            }
        raise AssertionError(path)

    monkeypatch.setitem(monitor_session.__globals__, "request_json", request)
    final, _run_id = monitor_session(
        "http://fixture",
        900,
        0,
        tmp_path / "report.json",
        report,
    )

    assert final["checkpoint"]["coverage"]["attachment_documents_parsed"] == 2
    assert (
        report["run"]["checkpoint"]["coverage"]["attachment_employer_candidates_extracted"]
        == 3
    )
