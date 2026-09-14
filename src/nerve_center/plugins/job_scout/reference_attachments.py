"""Bounded public civic-directory attachment discovery and parsing."""

from __future__ import annotations

import base64
import csv
import io
import json
import re
from dataclasses import dataclass
from datetime import timedelta
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

import httpx
from pypdf import PdfReader

from nerve_center.discovery.fetching import HttpFetcher, ResponseTooLargeError
from nerve_center.discovery.normalization import canonicalize_url
from nerve_center.discovery.search import SearchChallengeError
from nerve_center.persistence.discovery import SearchCacheRepository

MAX_ATTACHMENT_BYTES = 4_000_000
MAX_ATTACHMENT_LINKS_PER_REFERENCE = 6
MAX_ATTACHMENT_FETCHES_PER_REFERENCE = 2
MAX_ATTACHMENT_DOCUMENTS_PER_REFERENCE = 3
MAX_ATTACHMENT_CANDIDATES_PER_REFERENCE = 12
MAX_PDF_PAGES = 8
MAX_TABULAR_ROWS = 500
MAX_JSON_NODES = 2_000
MAX_XLSX_UNCOMPRESSED_BYTES = 12_000_000
MAX_XLSX_SHEETS = 4

_SUPPORTED_EXTENSIONS = {".pdf", ".csv", ".tsv", ".json", ".xlsx"}
_UNSUPPORTED_DOCUMENT_EXTENSIONS = {".doc", ".docx", ".xls", ".ods", ".zip"}
_EMPLOYER_FIELDS = {
    "business",
    "businessname",
    "company",
    "companyname",
    "employer",
    "employername",
    "organization",
    "organizationname",
}
_EMPLOYER_CONTAINERS = {
    "businesses",
    "companies",
    "employers",
    "organizations",
}
_METADATA_FIELDS = {
    "author",
    "creator",
    "copyrightholder",
    "provider",
    "publisher",
}
_DIRECTORY_CONTEXT = re.compile(
    r"\b(?:employer|employers|company|companies|business|businesses|"
    r"workforce|economic\s+development|largest|major|top)\b",
    re.IGNORECASE,
)
_EMPLOYER_HEADING = re.compile(
    r"\b(?:(?:major|top|largest)\s+employers?|employer\s+directory|"
    r"company\s+directory|business\s+directory)\b",
    re.IGNORECASE,
)
_STOP_HEADING = re.compile(
    r"^(?:contact|resources?|about|news|events?|staff|leadership|footer)$",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class AttachmentLink:
    """One plausible attachment discovered from an inspected civic page."""

    parent_url: str
    url: str
    link_text: str
    hinted_content_type: str = ""
    format_hint: str = "unsupported"

    @property
    def supported(self) -> bool:
        return self.format_hint in {"pdf", "csv", "tsv", "json", "xlsx"}


@dataclass(frozen=True, slots=True)
class DirectoryDocument:
    """One bounded attachment response with cache and redirect provenance."""

    url: str
    content: bytes
    text: str
    content_type: str
    cache_status: str


@dataclass(frozen=True, slots=True)
class DirectoryParseResult:
    """Safe bounded parse result for one public directory document."""

    candidates: tuple[str, ...] = ()
    extraction_method: str = "unsupported"
    status: str = "unsupported"
    units_inspected: int = 0
    detail: str = ""


class AttachmentDocumentError(RuntimeError):
    """A public attachment is not currently safe or useful to parse."""


class _AttachmentLinkParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.links: list[tuple[str, str, str, str]] = []
        self._heading_tag: str | None = None
        self._heading_parts: list[str] = []
        self._last_heading = ""
        self._anchor_href: str | None = None
        self._anchor_type = ""
        self._anchor_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if len(tag) == 2 and tag.startswith("h") and tag[1].isdigit():
            self._heading_tag = tag
            self._heading_parts = []
        if tag == "a" and self._anchor_href is None:
            href = values.get("href")
            if href:
                self._anchor_href = href
                self._anchor_type = values.get("type") or ""
                self._anchor_parts = []

    def handle_data(self, data: str) -> None:
        if self._heading_tag is not None:
            self._heading_parts.append(data)
        if self._anchor_href is not None:
            self._anchor_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._heading_tag == tag:
            self._last_heading = _clean_text("".join(self._heading_parts))[:300]
            self._heading_tag = None
            self._heading_parts = []
        if tag == "a" and self._anchor_href is not None:
            href = self._anchor_href
            text = _clean_text("".join(self._anchor_parts))[:300]
            absolute = urljoin(self.base_url, href)
            self.links.append((absolute, text, self._anchor_type[:200], self._last_heading))
            self._anchor_href = None
            self._anchor_type = ""
            self._anchor_parts = []


def discover_directory_attachments(
    parent_url: str,
    html: str,
    *,
    limit: int = MAX_ATTACHMENT_LINKS_PER_REFERENCE,
) -> list[AttachmentLink]:
    """Find bounded employer-oriented public document links from one civic page."""

    if limit < 1:
        return []
    parser = _AttachmentLinkParser(parent_url)
    try:
        parser.feed(html[:2_000_000])
        parser.close()
    except (ValueError, TypeError):
        return []
    found: list[AttachmentLink] = []
    seen: set[str] = set()
    for raw_url, text, hinted_type, heading in parser.links:
        split = urlsplit(raw_url)
        if split.scheme not in {"http", "https"}:
            continue
        try:
            url = canonicalize_url(raw_url)
        except ValueError:
            continue
        if url == canonicalize_url(parent_url) or url in seen:
            continue
        context = _clean_text(f"{heading} {text} {split.path}")
        if not _DIRECTORY_CONTEXT.search(context):
            continue
        format_hint = infer_document_format(url, hinted_type)
        suffix = _path_suffix(url)
        if format_hint == "unsupported" and suffix not in _UNSUPPORTED_DOCUMENT_EXTENSIONS:
            continue
        seen.add(url)
        found.append(
            AttachmentLink(
                parent_url=canonicalize_url(parent_url),
                url=url,
                link_text=text,
                hinted_content_type=hinted_type,
                format_hint=format_hint,
            )
        )
        if len(found) >= min(limit, MAX_ATTACHMENT_LINKS_PER_REFERENCE):
            break
    found.sort(key=lambda item: not item.supported)
    return found


class PublicAttachmentFetcher:
    """Canonical-URL cached attachment acquisition with bounded retry behavior."""

    cache_provider = "public_reference_attachment:v1"

    def __init__(
        self,
        cache: SearchCacheRepository,
        *,
        fetcher: HttpFetcher | None = None,
        max_bytes: int = MAX_ATTACHMENT_BYTES,
    ) -> None:
        self.cache = cache
        self.fetcher = fetcher or HttpFetcher()
        self.max_bytes = max(1, max_bytes)

    def cache_status(self, url: str) -> str:
        cached = self.cache.get(self.cache_provider, canonicalize_url(url))
        if cached is None:
            return "miss"
        status = str(cached.get("status") or "")
        if status == "succeeded":
            return "hit"
        if status == "invalid":
            return "invalid"
        return "retry_deferred"

    async def fetch(self, url: str) -> DirectoryDocument:
        canonical_url = canonicalize_url(url)
        cached = self.cache.get(self.cache_provider, canonical_url)
        if cached is not None:
            status = str(cached.get("status") or "")
            if status == "succeeded":
                encoded = str(cached.get("content_b64") or "")
                try:
                    content = base64.b64decode(encoded, validate=True)
                except (ValueError, TypeError):
                    content = b""
                return DirectoryDocument(
                    url=str(cached.get("url") or canonical_url),
                    content=content,
                    text=str(cached.get("text") or ""),
                    content_type=str(cached.get("content_type") or ""),
                    cache_status="hit",
                )
            message = str(cached.get("message") or "Public attachment is cooling down.")
            if status == "invalid":
                raise AttachmentDocumentError(message)
            raise SearchChallengeError(message)

        try:
            response = await self.fetcher.get(
                canonical_url,
                headers={
                    "Accept": (
                        "application/pdf,text/csv,text/tab-separated-values,application/json,"
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,"
                        "application/octet-stream;q=0.5"
                    )
                },
                max_bytes=self.max_bytes,
            )
        except ResponseTooLargeError as error:
            message = "Public attachment exceeded the bounded response-size limit."
            self.mark_invalid(canonical_url, message)
            raise AttachmentDocumentError(message) from error
        except httpx.RequestError as error:
            message = "The public attachment could not be reached; retry later."
            self.cache.put(
                self.cache_provider,
                canonical_url,
                {"status": "failed", "message": message},
                ttl=timedelta(minutes=15),
            )
            raise SearchChallengeError(message) from error
        if response.challenged or response.throttled or response.status_code in {
            401,
            403,
            429,
        }:
            message = "A public attachment requested a cooldown; try again later."
            self.cache.put(
                self.cache_provider,
                canonical_url,
                {"status": "challenged", "message": message},
                ttl=timedelta(hours=1),
            )
            raise SearchChallengeError(message)
        if response.status_code >= 400:
            message = f"Public attachment fetch failed with HTTP {response.status_code}."
            self.cache.put(
                self.cache_provider,
                canonical_url,
                {"status": "failed", "message": message},
                ttl=timedelta(minutes=15),
            )
            raise SearchChallengeError(message)
        content = response.content or response.text.encode("utf-8", errors="replace")
        if len(content) > self.max_bytes:
            message = "Public attachment exceeded the bounded response-size limit."
            self.mark_invalid(canonical_url, message)
            raise AttachmentDocumentError(message)
        document = DirectoryDocument(
            url=response.url,
            content=content,
            text=response.text[:2_000_000],
            content_type=response.headers.get("content-type", ""),
            cache_status="miss",
        )
        self.cache.put(
            self.cache_provider,
            canonical_url,
            {
                "status": "succeeded",
                "url": document.url,
                "content_type": document.content_type,
                "text": document.text if _is_text_document(document.content_type) else "",
                "content_b64": base64.b64encode(content).decode("ascii"),
            },
            ttl=timedelta(days=1),
        )
        return document

    def mark_invalid(self, url: str, message: str) -> None:
        self.cache.put(
            self.cache_provider,
            canonicalize_url(url),
            {"status": "invalid", "message": _clean_text(message)[:500]},
            ttl=timedelta(days=1),
        )


def infer_document_format(url: str, content_type: str = "") -> str:
    """Resolve the initial supported document set from MIME and path evidence."""

    mime = content_type.split(";", 1)[0].strip().casefold()
    if mime == "application/pdf":
        return "pdf"
    if mime in {"text/csv", "application/csv"}:
        return "csv"
    if mime in {"text/tab-separated-values", "text/tsv"}:
        return "tsv"
    if mime in {"application/json", "text/json"} or mime.endswith("+json"):
        return "json"
    if mime == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
        return "xlsx"
    suffix = _path_suffix(url)
    return {
        ".pdf": "pdf",
        ".csv": "csv",
        ".tsv": "tsv",
        ".json": "json",
        ".xlsx": "xlsx",
    }.get(suffix, "unsupported")


def parse_directory_document(
    document: DirectoryDocument,
    *,
    candidate_limit: int = MAX_ATTACHMENT_CANDIDATES_PER_REFERENCE,
) -> DirectoryParseResult:
    """Parse one attachment only where document structure establishes employer context."""

    limit = max(0, min(candidate_limit, MAX_ATTACHMENT_CANDIDATES_PER_REFERENCE))
    if limit == 0:
        return DirectoryParseResult(
            extraction_method="candidate_limit",
            status="parsed",
        )
    format_name = infer_document_format(document.url, document.content_type)
    if format_name == "pdf":
        return _parse_pdf(document.content, limit)
    if format_name in {"csv", "tsv"}:
        text = document.text or document.content.decode("utf-8-sig", errors="replace")
        return _parse_delimited(text, "\t" if format_name == "tsv" else None, limit)
    if format_name == "json":
        text = document.text or document.content.decode("utf-8-sig", errors="replace")
        return _parse_json(text, limit)
    if format_name == "xlsx":
        return _parse_xlsx(document.content, limit)
    return DirectoryParseResult(
        extraction_method="unsupported",
        status="unsupported",
        detail="Unsupported public directory document format.",
    )


def _parse_pdf(content: bytes, limit: int) -> DirectoryParseResult:
    try:
        reader = PdfReader(io.BytesIO(content), strict=False)
        if reader.is_encrypted:
            return DirectoryParseResult(
                extraction_method="pdf_text",
                status="invalid",
                detail="Password-protected PDF is not parsed.",
            )
        parts: list[str] = []
        pages = min(len(reader.pages), MAX_PDF_PAGES)
        for page in reader.pages[:pages]:
            parts.append(page.extract_text() or "")
    except Exception as error:
        return DirectoryParseResult(
            extraction_method="pdf_text",
            status="invalid",
            detail=f"Malformed PDF: {type(error).__name__}",
        )
    candidates = _extract_employer_section_lines("\n".join(parts), limit)
    return DirectoryParseResult(
        candidates=tuple(candidates),
        extraction_method="pdf_text_employer_section",
        status="parsed",
        units_inspected=pages,
    )


def _parse_delimited(
    text: str,
    delimiter: str | None,
    limit: int,
) -> DirectoryParseResult:
    sample = text[:32_000]
    resolved = delimiter
    if resolved is None:
        try:
            resolved = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
        except csv.Error:
            resolved = ","
    try:
        rows = csv.reader(io.StringIO(text), delimiter=resolved)
        buffered: list[list[str]] = []
        for index, row in enumerate(rows):
            if index >= MAX_TABULAR_ROWS:
                break
            buffered.append(row)
    except (csv.Error, TypeError) as error:
        return DirectoryParseResult(
            extraction_method="delimited_employer_field",
            status="invalid",
            detail=f"Malformed delimited document: {type(error).__name__}",
        )
    header_row, employer_column = _find_employer_column(buffered[:10])
    if employer_column is None or header_row is None:
        return DirectoryParseResult(
            extraction_method="delimited_employer_field",
            status="parsed",
            units_inspected=len(buffered),
        )
    candidates: list[str] = []
    seen: set[str] = set()
    for row in buffered[header_row + 1 :]:
        value = row[employer_column] if employer_column < len(row) else ""
        _append_candidate(candidates, seen, value, limit)
        if len(candidates) >= limit:
            break
    return DirectoryParseResult(
        candidates=tuple(candidates),
        extraction_method="delimited_employer_field",
        status="parsed",
        units_inspected=len(buffered),
    )


def _parse_json(text: str, limit: int) -> DirectoryParseResult:
    try:
        document = json.loads(text)
    except json.JSONDecodeError as error:
        return DirectoryParseResult(
            extraction_method="json_employer_fields",
            status="invalid",
            detail=f"Malformed JSON: {error.msg}",
        )
    candidates: list[str] = []
    seen: set[str] = set()
    nodes = 0

    def walk(
        value: object,
        *,
        directory_context: bool = False,
        organization_context: bool = False,
        metadata_context: bool = False,
    ) -> None:
        nonlocal nodes
        if len(candidates) >= limit or nodes >= MAX_JSON_NODES:
            return
        nodes += 1
        if isinstance(value, list):
            for item in value:
                walk(
                    item,
                    directory_context=directory_context,
                    organization_context=organization_context,
                    metadata_context=metadata_context,
                )
            return
        if not isinstance(value, dict):
            if organization_context and not metadata_context:
                _append_candidate(candidates, seen, value, limit)
            return
        kind = value.get("@type")
        kinds = {
            str(item).casefold()
            for item in (kind if isinstance(kind, list) else [kind])
            if item is not None
        }
        if "itemlist" in kinds:
            walk(value.get("itemListElement", []), directory_context=True)
            return
        if directory_context and kinds & {"corporation", "localbusiness", "organization"}:
            _append_candidate(candidates, seen, value.get("name"), limit)
        if organization_context and not metadata_context:
            _append_candidate(candidates, seen, value.get("name"), limit)
        for key, item in value.items():
            normalized = _normalized_field(key)
            child_metadata = metadata_context or normalized in _METADATA_FIELDS
            employer_field = normalized in _EMPLOYER_FIELDS
            directory_field = normalized in _EMPLOYER_CONTAINERS
            if employer_field and isinstance(item, str) and not child_metadata:
                _append_candidate(candidates, seen, item, limit)
            else:
                walk(
                    item,
                    directory_context=directory_context or directory_field,
                    organization_context=(employer_field or directory_field),
                    metadata_context=child_metadata,
                )

    walk(document)
    return DirectoryParseResult(
        candidates=tuple(candidates),
        extraction_method="json_employer_fields",
        status="parsed",
        units_inspected=min(nodes, MAX_JSON_NODES),
    )


def _parse_xlsx(content: bytes, limit: int) -> DirectoryParseResult:
    try:
        with ZipFile(io.BytesIO(content)) as archive:
            infos = archive.infolist()
            if any(info.flag_bits & 0x1 for info in infos):
                return DirectoryParseResult(
                    extraction_method="xlsx_employer_column",
                    status="invalid",
                    detail="Password-protected XLSX is not parsed.",
                )
            if sum(info.file_size for info in infos) > MAX_XLSX_UNCOMPRESSED_BYTES:
                return DirectoryParseResult(
                    extraction_method="xlsx_employer_column",
                    status="invalid",
                    detail="XLSX uncompressed size exceeds the bounded limit.",
                )
            shared = _xlsx_shared_strings(archive)
            worksheet_names = sorted(
                name
                for name in archive.namelist()
                if name.startswith("xl/worksheets/") and name.endswith(".xml")
            )[:MAX_XLSX_SHEETS]
            rows: list[list[str]] = []
            for name in worksheet_names:
                rows.extend(_xlsx_rows(archive.read(name), shared, MAX_TABULAR_ROWS - len(rows)))
                if len(rows) >= MAX_TABULAR_ROWS:
                    break
    except (BadZipFile, KeyError, ElementTree.ParseError, ValueError) as error:
        return DirectoryParseResult(
            extraction_method="xlsx_employer_column",
            status="invalid",
            detail=f"Malformed XLSX: {type(error).__name__}",
        )
    header_row, employer_column = _find_employer_column(rows[:20])
    candidates: list[str] = []
    seen: set[str] = set()
    if header_row is not None and employer_column is not None:
        for row in rows[header_row + 1 :]:
            value = row[employer_column] if employer_column < len(row) else ""
            _append_candidate(candidates, seen, value, limit)
            if len(candidates) >= limit:
                break
    return DirectoryParseResult(
        candidates=tuple(candidates),
        extraction_method="xlsx_employer_column",
        status="parsed",
        units_inspected=len(rows),
    )


def _extract_employer_section_lines(text: str, limit: int) -> list[str]:
    lines = [_clean_text(line) for line in text.splitlines()]
    candidates: list[str] = []
    seen: set[str] = set()
    in_section = False
    lines_after_marker = 0
    for line in lines:
        if not line:
            continue
        if _EMPLOYER_HEADING.search(line):
            in_section = True
            lines_after_marker = 0
            continue
        normalized = _normalized_field(line)
        if normalized in _EMPLOYER_FIELDS or normalized in {
            "employeremployees",
            "companyemployees",
            "businessemployees",
        }:
            in_section = True
            lines_after_marker = 0
            continue
        if not in_section:
            continue
        if _STOP_HEADING.match(line):
            break
        lines_after_marker += 1
        if lines_after_marker > 80:
            break
        _append_candidate(candidates, seen, line, limit, strip_numeric_suffix=True)
        if len(candidates) >= limit:
            break
    return candidates


def _find_employer_column(rows: list[list[str]]) -> tuple[int | None, int | None]:
    for row_index, row in enumerate(rows):
        for column_index, value in enumerate(row):
            if _normalized_field(value) in _EMPLOYER_FIELDS:
                return row_index, column_index
    return None, None


def _xlsx_shared_strings(archive: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
    return [
        "".join(node.text or "" for node in item.iter() if _local_name(node.tag) == "t")
        for item in root
        if _local_name(item.tag) == "si"
    ]


def _xlsx_rows(content: bytes, shared: list[str], limit: int) -> list[list[str]]:
    if limit <= 0:
        return []
    root = ElementTree.fromstring(content)
    rows: list[list[str]] = []
    for row in (node for node in root.iter() if _local_name(node.tag) == "row"):
        values: dict[int, str] = {}
        for cell in (node for node in row if _local_name(node.tag) == "c"):
            ref = cell.attrib.get("r", "A1")
            column = _xlsx_column_index(ref)
            cell_type = cell.attrib.get("t", "")
            value = ""
            if cell_type == "inlineStr":
                value = "".join(
                    node.text or "" for node in cell.iter() if _local_name(node.tag) == "t"
                )
            else:
                raw = next(
                    (node.text or "" for node in cell if _local_name(node.tag) == "v"),
                    "",
                )
                if cell_type == "s" and raw.isdigit():
                    index = int(raw)
                    value = shared[index] if index < len(shared) else ""
                else:
                    value = raw
            values[column] = _clean_text(value)
        if values:
            width = min(max(values) + 1, 64)
            rows.append([values.get(index, "") for index in range(width)])
        if len(rows) >= limit:
            break
    return rows


def _xlsx_column_index(reference: str) -> int:
    letters = "".join(character for character in reference if character.isalpha()).upper()
    value = 0
    for character in letters:
        value = value * 26 + (ord(character) - ord("A") + 1)
    return max(value - 1, 0)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _append_candidate(
    candidates: list[str],
    seen: set[str],
    raw: object,
    limit: int,
    *,
    strip_numeric_suffix: bool = False,
) -> None:
    candidate = _clean_text(str(raw or "")).strip(" |:-")
    if strip_numeric_suffix:
        candidate = re.sub(
            r"\s+\d[\d,]*(?:\.\d+)?(?:\s+employees?)?\s*$",
            "",
            candidate,
            flags=re.IGNORECASE,
        ).strip(" |:-")
    candidate = re.sub(r"^\d+[.)]\s+", "", candidate).strip()
    key = candidate.casefold()
    if (
        len(candidates) >= limit
        or not 2 <= len(candidate) <= 100
        or not 1 <= len(candidate.split()) <= 10
        or not re.search(r"[A-Za-z]", candidate)
        or key in seen
        or _normalized_field(candidate) in _EMPLOYER_FIELDS
        or candidate.casefold().startswith(("http://", "https://", "www."))
        or "@" in candidate
    ):
        return
    seen.add(key)
    candidates.append(candidate)


def _path_suffix(url: str) -> str:
    path = urlsplit(url).path.casefold()
    extensions = _SUPPORTED_EXTENSIONS | _UNSUPPORTED_DOCUMENT_EXTENSIONS
    return next((suffix for suffix in extensions if path.endswith(suffix)), "")


def _normalized_field(value: object) -> str:
    return re.sub(r"[^a-z]", "", str(value or "").casefold())


def _clean_text(value: str) -> str:
    return " ".join(value.split())


def _is_text_document(content_type: str) -> bool:
    mime = content_type.split(";", 1)[0].strip().casefold()
    return mime.startswith("text/") or "json" in mime or "xml" in mime
