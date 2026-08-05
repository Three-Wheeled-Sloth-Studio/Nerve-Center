"""Durable Job Scout configuration and deterministic search-term discovery."""

from __future__ import annotations

import re
from collections import Counter

from pydantic import BaseModel, ConfigDict, Field, field_validator

from nerve_center.config import Settings
from nerve_center.profile.models import CanonicalCareerProfile, ClaimDecision, SourceDocument

_STORAGE_NAMESPACE = "job_scout"
_CONFIG_FILE = "config.json"
_TOKEN_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9+#./-]{1,}")
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


def clean_list(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value.strip() for value in values if value.strip()))


class JobScoutConfiguration(BaseModel):
    """Module-owned configuration used by setup and scheduled scans."""

    model_config = ConfigDict(extra="forbid")

    resume_document_id: str | None = None
    resume_file_name: str | None = None
    target_titles: list[str] = Field(default_factory=list, max_length=40)
    locations: list[str] = Field(default_factory=list, max_length=40)
    remote_preference: str = Field(default="any", pattern="^(any|remote|hybrid|on_site)$")
    source_urls: list[str] = Field(default_factory=list, max_length=200)
    source_ids: list[str] = Field(default_factory=list, max_length=500)
    allowed_domains: list[str] = Field(default_factory=list, max_length=200)
    disallowed_domains: list[str] = Field(default_factory=list, max_length=200)
    manual_keywords: list[str] = Field(default_factory=list, max_length=100)
    # Accepted only so pre-0.12.1 configuration files continue to load. Earlier
    # versions mixed generated terms into this field, so it is intentionally
    # ignored and omitted when the configuration is written again.
    keywords: list[str] = Field(default_factory=list, max_length=100, exclude=True)
    broad_search_enabled: bool = False
    scan_interval_minutes: int = Field(default=1440, ge=5, le=10080)

    @field_validator(
        "target_titles",
        "locations",
        "source_urls",
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
    for sequence in sequences:
        for size in (3, 2):
            for index in range(len(sequence) - size + 1):
                window = sequence[index : index + size]
                if any(item is None for item in window):
                    continue
                terms = [item[0] for item in window if item is not None]
                technical = any(item[1] for item in window if item is not None)
                if not technical and not any(counts[term] >= 2 for term in terms):
                    continue
                phrase = " ".join(terms)
                phrase_counts[phrase] += 1
                phrase_strength[phrase] = sum(counts[term] for term in terms)

    ranked_phrases = [
        phrase
        for phrase, _count in sorted(
            phrase_counts.items(),
            key=lambda item: (
                -item[1],
                -phrase_strength[item[0]],
                -len(item[0].split()),
                item[0],
            ),
        )
    ][:20]
    ranked_tokens = [
        token
        for token, count in sorted(
            counts.items(), key=lambda item: (-item[1], -len(item[0]), item[0])
        )
        if count >= 2 or _token_is_technical_in_sequences(token, sequences)
    ][:15]
    return clean_list([*ranked_phrases, *ranked_tokens]), sum(counts.values())


def _looks_technical(value: str) -> bool:
    return (
        (value.isupper() and 2 <= len(value) <= 12)
        or any(character.isdigit() for character in value)
        or any(character in value for character in "+#./-")
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


def build_search_queries(
    configuration: JobScoutConfiguration,
    keywords: list[str],
) -> list[str]:
    anchors = configuration.target_titles or keywords[:5]
    locations = configuration.locations or [""]
    remote = " remote" if configuration.remote_preference == "remote" else ""
    queries: list[str] = []
    for anchor in anchors[:8]:
        for location in locations[:3]:
            location_part = f" {location}" if location else ""
            queries.append(f'"{anchor}"{location_part}{remote} jobs careers'.strip())
    return clean_list(queries)[:20]
