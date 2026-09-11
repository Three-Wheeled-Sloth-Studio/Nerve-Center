"""Source-aware Job Scout query portfolios, linting, and coverage-gap analysis."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from urllib.parse import urlparse

from nerve_center.discovery.models import (
    DiscoverySource,
    NormalizedJobOpening,
    SourceKind,
)
from nerve_center.plugins.job_scout.discovery_learning import DiscoveryStrategySnapshot
from nerve_center.plugins.job_scout.settings import clean_list
from nerve_center.scoring.location import opening_matches_market

GENERIC_TITLE_TERMS = {
    "chief",
    "director",
    "engineer",
    "head",
    "lead",
    "manager",
    "officer",
    "principal",
    "senior",
    "specialist",
    "vice",
}
STRUCTURED_SOURCE_KINDS = {
    SourceKind.GREENHOUSE,
    SourceKind.LEVER,
    SourceKind.ASHBY,
    SourceKind.SITEMAP,
}
ATS_DOMAINS = (
    "greenhouse.io",
    "lever.co",
    "ashbyhq.com",
)


@dataclass(frozen=True, slots=True)
class SourceCapabilities:
    source_path: str
    site_restricted: bool
    include_location: bool
    include_employer_archetype: bool
    include_jobs_terms: bool


@dataclass(frozen=True, slots=True)
class CompiledQuery:
    query: str
    source_path: str
    warnings: tuple[str, ...]
    valid: bool


@dataclass(frozen=True, slots=True)
class QueryLintResult:
    valid: bool
    warnings: tuple[str, ...]


def source_capabilities(source_domain: str) -> SourceCapabilities:
    domain = _clean_domain(source_domain)
    if domain in {"", "web"}:
        return SourceCapabilities(
            source_path="broad_web",
            site_restricted=False,
            include_location=True,
            include_employer_archetype=True,
            include_jobs_terms=True,
        )
    if any(domain == item or domain.endswith(f".{item}") for item in ATS_DOMAINS):
        return SourceCapabilities(
            source_path="structured_ats_xray",
            site_restricted=True,
            include_location=False,
            include_employer_archetype=False,
            include_jobs_terms=False,
        )
    return SourceCapabilities(
        source_path="site_search",
        site_restricted=True,
        include_location=True,
        include_employer_archetype=True,
        include_jobs_terms=False,
    )


def build_query_portfolio(
    *,
    target_titles: list[str],
    keywords: list[str],
    locations: list[str],
    source_domains: list[str],
    limit: int = 96,
) -> list[dict[str, str]]:
    """Build materially different, bounded search hypotheses.

    Buckets are emitted round-robin across hypothesis family and source path so a
    high-recall broad-web family cannot consume the cap before other source paths
    are represented. ATS x-ray strategies deliberately defer geography to the
    structured posting after retrieval.
    """

    titles = clean_list(target_titles)
    terms = clean_list(keywords)
    places = clean_list(locations) or [""]
    domains = clean_list(["web", *source_domains]) or ["web"]
    direct = titles or ["product management"]
    title_tokens = _tokens(" ".join(direct))
    capability_terms = [
        item for item in terms if _tokens(item) - title_tokens and not _generic_anchor(item)
    ]
    adjacent = _adjacent_anchors(direct, capability_terms)
    seniority = _seniority_variants(direct)
    capabilities = capability_terms[:6]
    archetypes = _archetype_terms(capability_terms)

    families: list[tuple[str, list[tuple[str, str]]]] = [
        ("direct_role", [(item, "") for item in direct[:6]]),
        ("adjacent_role", [(item, "") for item in adjacent[:5]]),
        ("seniority_variant", [(item, "") for item in seniority[:5]]),
        ("domain_capability", [(item, "") for item in capabilities[:6]]),
        ("employer_archetype", [(direct[0], item) for item in archetypes[:4]]),
        # Find plausible local employers first, even when no matching opening is
        # currently indexed. Their durable career surfaces can then be revisited
        # independently of public-search wording.
        ("local_employer", [(item, "") for item in archetypes[:4]]),
    ]

    buckets: list[list[dict[str, str]]] = []
    evidence_terms = [*titles, *terms]
    for family, hypotheses in families:
        if not hypotheses:
            continue
        for domain in domains:
            source = source_capabilities(domain)
            if family == "employer_archetype" and not source.include_employer_archetype:
                continue
            if family == "local_employer" and source.source_path != "broad_web":
                continue
            source_locations = places if source.include_location else [""]
            bucket: list[dict[str, str]] = []
            for anchor, archetype in hypotheses:
                for location in source_locations[:6]:
                    dimensions = {
                        "kind": "public_search",
                        "hypothesis_family": family,
                        "anchor": anchor,
                        "source_domain": _clean_domain(domain) or "web",
                        "source_path": source.source_path,
                    }
                    if location:
                        dimensions["location"] = location
                    if archetype:
                        dimensions["employer_archetype"] = archetype
                    compiled = compile_strategy_query(
                        dimensions,
                        evidence_terms=evidence_terms,
                    )
                    if compiled.valid:
                        bucket.append(dimensions)
            if bucket:
                buckets.append(bucket)

    result: list[dict[str, str]] = []
    seen_queries: set[tuple[str, str]] = set()
    while buckets and len(result) < limit:
        remaining: list[list[dict[str, str]]] = []
        for bucket in buckets:
            accepted = False
            while bucket and not accepted:
                dimensions = bucket.pop(0)
                compiled = compile_strategy_query(
                    dimensions,
                    evidence_terms=evidence_terms,
                )
                identity = (compiled.source_path, compiled.query.casefold())
                if compiled.valid and identity not in seen_queries:
                    seen_queries.add(identity)
                    result.append(dimensions)
                    accepted = True
                    if len(result) >= limit:
                        break
            if bucket:
                remaining.append(bucket)
        buckets = remaining
    return result


def compile_strategy_query(
    dimensions: dict[str, str],
    *,
    evidence_terms: Iterable[str] = (),
) -> CompiledQuery:
    anchor = " ".join(dimensions.get("anchor", "").split()).strip()
    location = " ".join(dimensions.get("location", "").split()).strip()
    source_domain = _clean_domain(dimensions.get("source_domain", "web")) or "web"
    archetype = " ".join(dimensions.get("employer_archetype", "").split()).strip()
    exclusions = " ".join(dimensions.get("exclude", "").split()).strip()
    technology = " ".join(dimensions.get("technology", "").split()).strip()
    requirement = " ".join(dimensions.get("requirement", "").split()).strip()
    capabilities = source_capabilities(source_domain)
    lint = lint_query_dimensions(
        dimensions,
        evidence_terms=evidence_terms,
        capabilities=capabilities,
    )
    warnings = list(lint.warnings)
    if not lint.valid:
        return CompiledQuery("", capabilities.source_path, tuple(warnings), False)

    parts: list[str] = []
    if anchor:
        parts.append(f'"{anchor}"')
    if location and capabilities.include_location:
        parts.append(location)
    elif location:
        warnings.append("location_deferred_to_post_fetch")
    if archetype and capabilities.include_employer_archetype:
        parts.append(archetype)
    if technology:
        parts.append(technology)
    if requirement:
        parts.append(requirement)
    if capabilities.include_jobs_terms:
        parts.append("jobs careers")
    if exclusions:
        parts.extend(f"-{item}" for item in _split_terms(exclusions))
    query = " ".join(clean_list(parts)).strip()
    if capabilities.site_restricted:
        query = f"site:{source_domain} {query}".strip()
    return CompiledQuery(
        query,
        capabilities.source_path,
        tuple(clean_list(warnings)),
        bool(query),
    )


def lint_query_dimensions(
    dimensions: dict[str, str],
    *,
    evidence_terms: Iterable[str] = (),
    capabilities: SourceCapabilities | None = None,
) -> QueryLintResult:
    warnings: list[str] = []
    anchor = " ".join(dimensions.get("anchor", "").split()).strip()
    if not anchor:
        return QueryLintResult(False, ("missing_anchor",))
    if _generic_anchor(anchor):
        return QueryLintResult(False, ("catch_all_anchor",))

    exclusions = _split_terms(dimensions.get("exclude", ""))
    anchor_tokens = _tokens(anchor)
    contradictory = sorted(anchor_tokens & {_normalize_term(item) for item in exclusions})
    if contradictory:
        return QueryLintResult(
            False,
            tuple(f"contradictory_exclusion:{item}" for item in contradictory),
        )

    fields = [
        dimensions.get("anchor", ""),
        dimensions.get("location", ""),
        dimensions.get("employer_archetype", ""),
        dimensions.get("technology", ""),
        dimensions.get("requirement", ""),
    ]
    normalized_fields = [
        _normalize_phrase(item) for item in fields if _normalize_phrase(item)
    ]
    duplicates = {item for item in normalized_fields if normalized_fields.count(item) > 1}
    if duplicates:
        warnings.extend(f"duplicate_constraint:{item}" for item in sorted(duplicates))

    supported = _tokens(" ".join(str(item) for item in evidence_terms))
    for key in ("technology", "requirement"):
        value = dimensions.get(key, "").strip()
        if value and (_tokens(value) - supported):
            return QueryLintResult(False, (f"unsupported_{key}",))

    effective = capabilities or source_capabilities(
        dimensions.get("source_domain", "web")
    )
    if (
        effective.source_path == "structured_ats_xray"
        and dimensions.get("location", "").strip()
    ):
        warnings.append("source_specific_location_omitted")
    return QueryLintResult(True, tuple(clean_list(warnings)))


def build_coverage_gap_profile(
    *,
    target_titles: list[str],
    keywords: list[str],
    locations: list[str],
    remote_preference: str,
    strategies: list[DiscoveryStrategySnapshot],
    openings: list[NormalizedJobOpening],
    sources: list[DiscoverySource],
) -> dict[str, list[str]]:
    """Return a small deterministic requested-vs-observed discovery gap profile."""

    gaps: dict[str, list[str]] = {
        "role": [],
        "domain_capability": [],
        "seniority": [],
        "geography": [],
        "work_arrangement": [],
        "employer_archetype": [],
        "source": [],
        "query_family": [],
    }
    corpus = " ".join(f"{item.title} {item.description}" for item in openings).casefold()
    corpus_tokens = _tokens(corpus)

    for title in clean_list(target_titles)[:6]:
        role_tokens = _tokens(title) - GENERIC_TITLE_TERMS
        if role_tokens and not any(
            _coverage_overlap(
                role_tokens,
                _tokens(item.title) - GENERIC_TITLE_TERMS,
            )
            >= 0.5
            for item in openings
        ):
            gaps["role"].append(title)

    title_tokens = _tokens(" ".join(target_titles))
    for term in clean_list(keywords)[:10]:
        useful = _tokens(term) - title_tokens
        if useful and not useful.issubset(corpus_tokens):
            gaps["domain_capability"].append(term)

    requested_seniority = clean_list(
        [level for title in target_titles for level in _seniority_levels(title)]
    )
    observed_seniority = {
        level for opening in openings for level in _seniority_levels(opening.title)
    }
    gaps["seniority"] = [
        item for item in requested_seniority if item not in observed_seniority
    ]

    for location in clean_list(locations)[:8]:
        if not any(opening_matches_market(item, location) for item in openings):
            gaps["geography"].append(location)

    preferred = remote_preference.strip().casefold()
    if preferred not in {"", "any"} and not any(
        item.work_arrangement.value == preferred for item in openings
    ):
        gaps["work_arrangement"].append(preferred)

    archetype_strategies = [
        item
        for item in strategies
        if item.dimensions.get("hypothesis_family") == "employer_archetype"
    ]
    gaps["employer_archetype"] = clean_list(
        [
            item.dimensions.get("employer_archetype", "")
            for item in archetype_strategies
            if (
                item.opportunities_retained
                + item.companies_discovered
                + item.career_sources_resolved
                == 0
            )
        ]
    )[:6]

    configured_domains = clean_list(
        [
            _clean_domain(item.dimensions.get("source_domain", ""))
            for item in strategies
        ]
    )
    gaps["source"] = [
        item
        for item in configured_domains
        if item not in {"", "web"} and not _source_domain_observed(item, sources)
    ][:6]

    productive_families = {
        item.dimensions.get("hypothesis_family", "")
        for item in strategies
        if item.attempts > 0
        and (
            item.opportunities_retained
            + item.companies_discovered
            + item.career_sources_resolved
            > 0
        )
    }
    planned_families = clean_list(
        [item.dimensions.get("hypothesis_family", "") for item in strategies]
    )
    gaps["query_family"] = [
        item for item in planned_families if item not in productive_families
    ][:6]

    return {key: clean_list(value)[:8] for key, value in gaps.items() if value}


def preferred_structured_source_ids(sources: list[DiscoverySource]) -> set[str]:
    return {
        item.id
        for item in sources
        if item.enabled and item.kind in STRUCTURED_SOURCE_KINDS
    }


def _source_domain_observed(domain: str, sources: list[DiscoverySource]) -> bool:
    source_kind = None
    if domain == "greenhouse.io" or domain.endswith(".greenhouse.io"):
        source_kind = SourceKind.GREENHOUSE
    elif domain == "lever.co" or domain.endswith(".lever.co"):
        source_kind = SourceKind.LEVER
    elif domain == "ashbyhq.com" or domain.endswith(".ashbyhq.com"):
        source_kind = SourceKind.ASHBY
    if source_kind is not None and any(item.kind is source_kind for item in sources):
        return True
    return any(_clean_domain(item.base_url) == domain for item in sources)


def _adjacent_anchors(
    target_titles: list[str],
    capability_terms: list[str],
) -> list[str]:
    result: list[str] = []
    for term in capability_terms[:4]:
        words = [
            item
            for item in re.findall(r"[A-Za-z0-9]+", term)
            if item.casefold() not in GENERIC_TITLE_TERMS
        ]
        if words:
            result.append(" ".join([*words[:3], "lead"]))
    for title in target_titles:
        core = [
            item
            for item in re.findall(r"[A-Za-z0-9]+", title)
            if item.casefold() not in GENERIC_TITLE_TERMS
        ]
        if core:
            result.append(f"{' '.join(core[:4])} owner")
    return clean_list(result)


def _seniority_variants(target_titles: list[str]) -> list[str]:
    result: list[str] = []
    for title in target_titles:
        core = [
            item
            for item in re.findall(r"[A-Za-z0-9]+", title)
            if item.casefold() not in GENERIC_TITLE_TERMS
        ]
        if not core:
            continue
        core_text = " ".join(core[:5])
        result.extend([f"Head of {core_text}", f"Principal {core_text}"])
    return clean_list(result)


def _archetype_terms(capability_terms: list[str]) -> list[str]:
    result: list[str] = []
    for term in capability_terms:
        tokens = _tokens(term)
        if not tokens or tokens & {
            "agile",
            "roadmap",
            "stakeholder",
            "workflow",
            "leadership",
        }:
            continue
        result.append(f"{term} company")
    return clean_list(result)


def _seniority_levels(value: str) -> list[str]:
    normalized = _normalize_phrase(value)
    levels = []
    for level in (
        "chief",
        "vice president",
        "director",
        "head",
        "principal",
        "senior",
        "lead",
    ):
        if level in normalized:
            levels.append(level)
    return levels


def _generic_anchor(value: str) -> bool:
    tokens = _tokens(value)
    return bool(tokens) and tokens.issubset(GENERIC_TITLE_TERMS)


def _split_terms(value: str) -> list[str]:
    return clean_list(re.split(r"[,;\s]+", value.strip()))


def _tokens(value: str) -> set[str]:
    return {
        _normalize_term(item)
        for item in re.findall(r"[A-Za-z0-9]+", value)
        if len(item) > 1
    }


def _normalize_term(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "", value.casefold())
    aliases = {
        "management": "manager",
        "products": "product",
    }
    return aliases.get(normalized, normalized)


def _normalize_phrase(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def _coverage_overlap(left: set[str], right: set[str]) -> float:
    return len(left & right) / max(1, len(left | right))


def _clean_domain(value: str) -> str:
    raw = value.strip().casefold()
    if raw in {"", "web"}:
        return raw
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    return (parsed.hostname or raw).removeprefix("www.")
