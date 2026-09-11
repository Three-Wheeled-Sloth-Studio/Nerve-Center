"""Durable Job Scout configuration and deterministic search-term discovery."""

from __future__ import annotations

import re
from collections import Counter

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from nerve_center.config import Settings
from nerve_center.profile.models import CanonicalCareerProfile, ClaimDecision, SourceDocument

_STORAGE_NAMESPACE = "job_scout"
_CONFIG_FILE = "config.json"
_TOKEN_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9+#./-]{1,}")
DEFAULT_PUBLIC_JOB_BOARDS = [
    "indeed.com",
    "builtin.com",
    "wellfound.com",
    "ziprecruiter.com",
]
_STOPWORDS = {
    "about",
    "across",
    "after",
    "also",
    "and",
    "another",
    "any",
    "are",
    "because",
    "been",
    "before",
    "being",
    "between",
    "both",
    "built",
    "can",
    "company",
    "could",
    "developed",
    "during",
    "each",
    "experience",
    "for",
    "from",
    "have",
    "having",
    "including",
    "into",
    "job",
    "jobs",
    "led",
    "line",
    "more",
    "most",
    "other",
    "over",
    "page",
    "paragraph",
    "resume",
    "role",
    "roles",
    "skills",
    "some",
    "such",
    "summary",
    "than",
    "that",
    "the",
    "their",
    "them",
    "then",
    "these",
    "they",
    "this",
    "those",
    "through",
    "using",
    "was",
    "were",
    "which",
    "while",
    "with",
    "within",
    "work",
    "worked",
    "would",
    "years",
    "your",
}
_PHRASE_ONLY_TERMS = {
    "analytics",
    "capabilities",
    "compliance",
    "data",
    "delivery",
    "governance",
    "health",
    "management",
    "platforms",
    "product",
    "reporting",
    "risk",
    "strategy",
    "supporting",
    "workflows",
}
_NO_SINGLE_TERMS = _PHRASE_ONLY_TERMS | {
    "behavioral",
    "change",
    "client",
    "cross-functional",
    "enforcement",
    "executive",
    "financial",
    "improving",
    "leadership",
    "reducing",
    "regulatory",
    "stakeholder",
    "teams",
    "taxpayer",
    "workflow",
}
_WEAK_PHRASE_LEADS = {
    "building",
    "co-led",
    "creating",
    "developing",
    "driving",
    "leading",
    "managing",
    "reducing",
    "strengthening",
    "supporting",
    "using",
}
_TITLE_CUE = re.compile(
    r"\b(?:chief|vice president|vp|head|director|manager|lead|principal|senior|staff|"
    r"analyst|architect|engineer|designer|consultant|specialist|coordinator|"
    r"administrator|owner)\b",
    re.IGNORECASE,
)
_LOCATION = re.compile(
    r"^[A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){0,3},\s*[A-Z]{2}"
    r"(?:\s+\d{5})?$"
)
_RESUME_FIELD_SPLIT = re.compile(r"\s*(?:\||\u2022|\u00b7|\s+-\s+|\s+@\s+)\s*")


def clean_list(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = value.strip()
        identity = cleaned.casefold()
        if cleaned and identity not in seen:
            seen.add(identity)
            result.append(cleaned)
    return result


class JobScoutConfiguration(BaseModel):
    """Module-owned configuration used by setup and scheduled scans."""

    model_config = ConfigDict(extra="forbid")

    resume_document_id: str | None = None
    resume_file_name: str | None = None
    target_titles: list[str] = Field(default_factory=list, max_length=40)
    locations: list[str] = Field(default_factory=list, max_length=40)
    remote_preference: str = Field(default="any", pattern="^(any|remote|hybrid|on_site)$")
    source_urls: list[str] = Field(default_factory=list, max_length=200)
    public_job_boards: list[str] = Field(
        default_factory=lambda: list(DEFAULT_PUBLIC_JOB_BOARDS), max_length=20
    )
    source_ids: list[str] = Field(default_factory=list, max_length=500)
    allowed_domains: list[str] = Field(default_factory=list, max_length=200)
    disallowed_domains: list[str] = Field(default_factory=list, max_length=200)
    manual_keywords: list[str] = Field(default_factory=list, max_length=100)
    # Accepted only so pre-0.12.1 configuration files continue to load. Earlier
    # versions mixed generated terms into this field, so it is intentionally
    # ignored and omitted when the configuration is written again.
    keywords: list[str] = Field(default_factory=list, max_length=100, exclude=True)
    broad_search_enabled: bool = True
    scan_interval_minutes: int = Field(default=1440, ge=5, le=10080)
    full_score_limit: int = Field(default=25, ge=0, le=1000)
    full_score_failure_limit: int = Field(default=25, ge=1, le=1000)

    @field_validator(
        "target_titles",
        "locations",
        "source_urls",
        "public_job_boards",
        "source_ids",
        "allowed_domains",
        "disallowed_domains",
        "manual_keywords",
        "keywords",
        mode="after",
    )
    @classmethod
    def normalize_lists(cls, values: list[str]) -> list[str]:
        return clean_list(values)

    @model_validator(mode="after")
    def align_public_discovery_state(self) -> JobScoutConfiguration:
        self.broad_search_enabled = bool(self.public_job_boards)
        return self


class ResumeLoadRequest(BaseModel):
    path: str = Field(min_length=1, max_length=4096)
    analyze_resume: bool = False


class ResumeUploadRequest(BaseModel):
    file_name: str = Field(min_length=1, max_length=255)
    content_base64: str = Field(min_length=1, max_length=36_000_000)
    analyze_resume: bool = False


class JobScoutKeywordSummary(BaseModel):
    keywords: list[str]
    search_queries: list[str]
    evidence_terms: int


class JobScoutSuggestionSummary(BaseModel):
    target_titles: list[str]
    locations: list[str]


class JobScoutConfigurationStore:
    def __init__(self, settings: Settings) -> None:
        self.path = settings.module_data_dir(_STORAGE_NAMESPACE) / _CONFIG_FILE

    def load(self) -> JobScoutConfiguration:
        if not self.path.exists():
            return JobScoutConfiguration()
        return JobScoutConfiguration.model_validate_json(self.path.read_text(encoding="utf-8"))

    def save(self, configuration: JobScoutConfiguration) -> JobScoutConfiguration:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(configuration.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(self.path)
        return configuration


def discover_keywords(
    configuration: JobScoutConfiguration,
    profile: CanonicalCareerProfile,
    document: SourceDocument | None,
) -> JobScoutKeywordSummary:
    explicit_phrases: list[str] = []
    evidence_text: list[str] = []
    for claim in profile.claims:
        if claim.decision is ClaimDecision.REJECTED:
            continue
        explicit_phrases.append(claim.label.strip())
        evidence_text.append(claim.statement)
    for hypothesis in profile.hypotheses:
        if hypothesis.decision.value != "disapproved":
            explicit_phrases.extend(
                (hypothesis.label.strip(), hypothesis.suggested_headline.strip())
            )
            evidence_text.append(hypothesis.summary)
    if document is not None:
        evidence_text.extend(segment.text for segment in document.segments)

    ranked_terms, evidence_terms = _rank_evidence_terms(evidence_text)
    keywords = clean_list(
        [
            *configuration.target_titles,
            *explicit_phrases,
            *configuration.manual_keywords,
            *ranked_terms,
        ]
    )[:40]
    return JobScoutKeywordSummary(
        keywords=keywords,
        search_queries=build_search_queries(configuration, keywords),
        evidence_terms=evidence_terms,
    )


def discover_suggestions(
    configuration: JobScoutConfiguration,
    profile: CanonicalCareerProfile,
    document: SourceDocument | None,
) -> JobScoutSuggestionSummary:
    title_candidates: list[str] = []
    location_candidates: list[str] = []
    for claim in profile.claims:
        if claim.decision is ClaimDecision.REJECTED:
            continue
        if claim.category.value == "role":
            title_candidates.append(claim.label)
        location_candidates.extend(_locations_from_text(claim.statement))
    for hypothesis in profile.hypotheses:
        if hypothesis.decision.value == "disapproved":
            continue
        if _looks_like_title(hypothesis.suggested_headline):
            title_candidates.append(hypothesis.suggested_headline)

    if document is not None:
        for segment in document.segments:
            for part in _RESUME_FIELD_SPLIT.split(segment.text):
                candidate = " ".join(part.split()).strip(" ,;:")
                if _looks_like_title(candidate):
                    title_candidates.append(candidate)
                location_candidates.extend(_locations_from_text(candidate))
            location_candidates.extend(_locations_from_text(segment.text))

    configured_titles = {value.casefold() for value in configuration.target_titles}
    configured_locations = {value.casefold() for value in configuration.locations}
    return JobScoutSuggestionSummary(
        target_titles=[
            value
            for value in clean_list(title_candidates)
            if value.casefold() not in configured_titles
        ][:8],
        locations=[
            value
            for value in clean_list(location_candidates)
            if value.casefold() not in configured_locations
        ][:8],
    )


def _rank_evidence_terms(values: list[str]) -> tuple[list[str], int]:
    sequences: list[list[tuple[str, bool] | None]] = []
    counts: Counter[str] = Counter()

    for value in values:
        sequence: list[tuple[str, bool] | None] = []
        for raw in _TOKEN_PATTERN.findall(value):
            normalized = raw.casefold().strip("./-")
            if (
                len(normalized) < 3
                or normalized in _STOPWORDS
                or normalized.isdigit()
            ):
                sequence.append(None)
                continue
            technical = _looks_technical(raw)
            sequence.append((normalized, technical))
            counts[normalized] += 1
        if sequence:
            sequences.append(sequence)

    phrase_counts: Counter[str] = Counter()
    phrase_strength: dict[str, int] = {}
    technical_phrases: set[str] = set()
    for sequence in sequences:
        for size in (3, 2):
            for index in range(len(sequence) - size + 1):
                window = sequence[index : index + size]
                if any(item is None for item in window):
                    continue
                terms = [item[0] for item in window if item is not None]
                technical = any(item[1] for item in window if item is not None)
                if not technical and not all(counts[term] >= 2 for term in terms):
                    continue
                phrase = " ".join(terms)
                if terms[0] in _WEAK_PHRASE_LEADS:
                    continue
                if terms[-1] == "capabilities" or (
                    terms[-1] == "product" and terms[0] in {"analytics", "data"}
                ):
                    continue
                phrase_counts[phrase] += 1
                phrase_strength[phrase] = sum(counts[term] for term in terms)
                if technical:
                    technical_phrases.add(phrase)

    ranked_phrases = [
        phrase
        for phrase, count in sorted(
            phrase_counts.items(),
            key=lambda item: (
                -item[1],
                -phrase_strength[item[0]],
                -len(item[0].split()),
                item[0],
            ),
        )
        if count >= 2 or phrase in technical_phrases
    ][:16]
    ranked_tokens = [
        token
        for token, _count in sorted(
            counts.items(), key=lambda item: (-item[1], -len(item[0]), item[0])
        )
        if _token_is_technical_in_sequences(token, sequences)
    ][:5]
    return clean_list([*ranked_phrases, *ranked_tokens]), sum(counts.values())


def _looks_technical(value: str) -> bool:
    normalized = value.casefold().strip("./-")
    return (
        (
            value.isupper()
            and 2 <= len(value) <= 12
            and normalized not in _NO_SINGLE_TERMS
            and normalized not in _STOPWORDS
        )
        or any(character.isdigit() for character in value)
        or any(character in normalized for character in "+#")
    )


def _token_is_technical_in_sequences(
    token: str,
    sequences: list[list[tuple[str, bool] | None]],
) -> bool:
    return any(
        item is not None and item[0] == token and item[1]
        for sequence in sequences
        for item in sequence
    )


def _looks_like_title(value: str) -> bool:
    cleaned = " ".join(value.split()).strip(" ,;:")
    words = cleaned.split()
    return (
        2 <= len(words) <= 10
        and len(cleaned) <= 100
        and _TITLE_CUE.search(cleaned) is not None
        and not re.search(
            r"[.!?]$|[()]|https?://|@\w+\.\w+|\b(?:19|20)\d{2}\b", cleaned
        )
    )


def _locations_from_text(value: str) -> list[str]:
    result: list[str] = []
    if re.search(r"\bremote\b", value, re.IGNORECASE):
        result.append("Remote")
    for part in _RESUME_FIELD_SPLIT.split(value):
        candidate = " ".join(part.split()).strip(" ,;:")
        if _LOCATION.fullmatch(candidate):
            result.append(re.sub(r"\s+\d{5}$", "", candidate))
    return result


def build_search_queries(
    configuration: JobScoutConfiguration,
    keywords: list[str],
) -> list[str]:
    anchors = configuration.target_titles or keywords[:5]
    locations = configuration.locations or [""]
    remote = " remote" if configuration.remote_preference == "remote" else ""
    base_queries: list[str] = []
    for anchor in anchors[:8]:
        for location in locations[:3]:
            location_part = f" {location}" if location else ""
            base_queries.append(f'"{anchor}"{location_part}{remote} jobs careers'.strip())
    domains: list[str] = []
    for board in configuration.public_job_boards:
        domain = board.casefold().removeprefix("https://").removeprefix("http://")
        domain = domain.split("/", 1)[0].removeprefix("www.")
        if domain:
            domains.append(domain)
    queries: list[str] = []
    for query in base_queries[:8]:
        queries.extend(f"site:{domain} {query}" for domain in domains)
        queries.append(query)
    return clean_list(queries)[:20]
