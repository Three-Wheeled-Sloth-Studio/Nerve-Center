"""Deterministic URL, text, date, and opening normalization helpers."""

from __future__ import annotations

import hashlib
import html
import re
from datetime import UTC, datetime
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import NAMESPACE_URL, uuid5

from nerve_center.discovery.models import WorkArrangement

_TRACKING_PARAMS = {
    "gh_jid",
    "gh_src",
    "lever-origin",
    "lever-source",
    "source",
    "src",
    "ref",
    "referrer",
    "utm_campaign",
    "utm_content",
    "utm_medium",
    "utm_source",
    "utm_term",
}
_WHITESPACE = re.compile(r"\s+")


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag in {"script", "style"}:
            self._ignored_depth += 1
        elif tag in {"br", "p", "div", "li", "tr", "h1", "h2", "h3", "h4"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self._ignored_depth:
            self._ignored_depth -= 1
        elif tag in {"p", "div", "li", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth:
            self.parts.append(data)


def clean_html_text(value: str | None) -> str:
    if not value:
        return ""
    parser = _TextExtractor()
    parser.feed(value)
    parser.close()
    lines = [_WHITESPACE.sub(" ", line).strip() for line in parser.parts]
    return "\n".join(line for line in lines if line)


def clean_text(value: object) -> str:
    return _WHITESPACE.sub(" ", html.unescape(str(value or ""))).strip()


def canonicalize_url(value: str) -> str:
    split = urlsplit(value.strip())
    scheme = split.scheme.lower() or "https"
    hostname = (split.hostname or "").lower()
    port = split.port
    netloc = hostname
    if port and not ((scheme == "https" and port == 443) or (scheme == "http" and port == 80)):
        netloc = f"{hostname}:{port}"
    path = re.sub(r"/{2,}", "/", split.path or "/")
    if path != "/":
        path = path.rstrip("/")
    query = [
        (key, item)
        for key, item in parse_qsl(split.query, keep_blank_values=True)
        if key.casefold() not in _TRACKING_PARAMS and not key.casefold().startswith("utm_")
    ]
    return urlunsplit((scheme, netloc, path, urlencode(sorted(query)), ""))


def canonical_domain(value: str) -> str:
    hostname = (urlsplit(value if "://" in value else f"https://{value}").hostname or "").lower()
    return hostname.removeprefix("www.")


def stable_company_id(domain: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"company|{canonical_domain(domain)}"))


def unresolved_company_domain(name: str) -> str:
    """Return a stable, non-routable identity for a named but unresolved employer."""

    normalized = clean_text(name).casefold()
    slug = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")[:80] or "company"
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]
    return f"{slug}-{digest}.unresolved.invalid"


def stable_source_id(kind: str, base_url: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"source|{kind}|{canonicalize_url(base_url)}"))


def stable_opening_id(
    company_domain: str,
    canonical_url: str,
    external_id: str | None = None,
) -> str:
    key = external_id or canonicalize_url(canonical_url)
    return str(uuid5(NAMESPACE_URL, f"job|{canonical_domain(company_domain)}|{key}"))


def opening_fingerprint(company_domain: str, title: str, location_text: str | None) -> str:
    normalized = "|".join(
        [
            canonical_domain(company_domain),
            clean_text(title).casefold(),
            clean_text(location_text).casefold(),
        ]
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def parse_datetime(value: object) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, (int, float)):
        seconds = value / 1000 if value > 10_000_000_000 else value
        try:
            return datetime.fromtimestamp(seconds, tz=UTC)
        except (OSError, OverflowError, ValueError):
            return None
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = datetime.strptime(text[:10], "%Y-%m-%d").replace(tzinfo=UTC)
        except ValueError:
            return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def infer_work_arrangement(*values: object) -> WorkArrangement:
    text = " ".join(clean_text(item).casefold() for item in values if item is not None)
    if "hybrid" in text:
        return WorkArrangement.HYBRID
    if any(token in text for token in ("remote", "telecommute", "work from home")):
        return WorkArrangement.REMOTE
    if any(token in text for token in ("on-site", "onsite", "on site", "in-office")):
        return WorkArrangement.ON_SITE
    return WorkArrangement.UNKNOWN
