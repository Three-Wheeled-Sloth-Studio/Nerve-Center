"""Durable Job Scout configuration and deterministic search-term discovery."""

from __future__ import annotations

import re
from collections import Counter

from pydantic import BaseModel, ConfigDict, Field, field_validator

from nerve_center.config import Settings
from nerve_center.profile.models import CanonicalCareerProfile, ClaimDecision, SourceDocument

_STORAGE_NAMESPACE = "job_scout"
_CONFIG_FILE = "config.json"
_TOKEN_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9+#./-]{2,}")
_STOPWORDS = {
    "about",
    "after",
    "also",
    "and",
    "are",
    "been",
    "before",
    "being",
    "built",
    "can",
    "company",
    "developed",
    "from",
    "have",
    "including",
    "into",
    "job",
    "jobs",
    "led",
    "manager",
    "more",
    "over",
    "role",
    "roles",
    "that",
    "the",
    "their",
    "this",
    "through",
    "using",
    "was",
    "were",
    "with",
    "work",
    "worked",
    "years",
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
    keywords: list[str] = Field(default_factory=list, max_length=100)
    broad_search_enabled: bool = False
    scan_interval_minutes: int = Field(default=1440, ge=5, le=10080)

    @field_validator(
        "target_titles",
        "locations",
        "source_urls",
        "source_ids",
        "allowed_domains",
        "disallowed_domains",
        "keywords",
        mode="after",
    )
    @classmethod
    def normalize_lists(cls, values: list[str]) -> list[str]:
        return clean_list(values)


class ResumeLoadRequest(BaseModel):
    path: str = Field(min_length=1, max_length=4096)
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
    phrases: list[str] = []
    evidence_text: list[str] = []
    for claim in profile.claims:
        if claim.decision is ClaimDecision.REJECTED:
            continue
        phrases.append(claim.label.strip())
        evidence_text.append(claim.statement)
    for hypothesis in profile.hypotheses:
        if hypothesis.decision.value != "disapproved":
            phrases.extend((hypothesis.label.strip(), hypothesis.suggested_headline.strip()))
            evidence_text.append(hypothesis.summary)
    if document is not None:
        evidence_text.append(document.analysis_text)

    counts: Counter[str] = Counter()
    for token in _TOKEN_PATTERN.findall("\n".join(evidence_text)):
        normalized = token.casefold().strip("./-")
        if normalized and normalized not in _STOPWORDS and not normalized.isdigit():
            counts[normalized] += 1
    ranked_tokens = [
        token
        for token, _count in sorted(
            counts.items(), key=lambda item: (-item[1], -len(item[0]), item[0])
        )
    ]
    keywords = clean_list(
        [*configuration.target_titles, *phrases, *configuration.keywords, *ranked_tokens]
    )[:40]
    return JobScoutKeywordSummary(
        keywords=keywords,
        search_queries=build_search_queries(configuration, keywords),
        evidence_terms=sum(counts.values()),
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
