"""Attachment-aware extension for location-sensitive Job Scout discovery."""

from __future__ import annotations

import re
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

from nerve_center.discovery.search import (
    ReferenceDocument,
    SearchChallengeError,
    SearchResult,
    UrlClassification,
)
from nerve_center.plugins.job_scout.discovery_learning import (
    DiscoverySessionModel,
    DiscoveryStrategySnapshot,
    JobScoutDiscoveryRepository,
    StrategyOutcome,
)
from nerve_center.plugins.job_scout.discovery_loop import (
    _RequestAllowance,
    _RequestAllowanceExhausted,
)
from nerve_center.plugins.job_scout.location_discovery import (
    LocationAwareJobScoutDiscoveryLoop,
)
from nerve_center.plugins.job_scout.reference_attachments import (
    MAX_ATTACHMENT_CANDIDATES_PER_REFERENCE,
    MAX_ATTACHMENT_DOCUMENTS_PER_REFERENCE,
    MAX_ATTACHMENT_FETCHES_PER_REFERENCE,
    AttachmentDocumentError,
    AttachmentLink,
    DirectoryDocument,
    PublicAttachmentFetcher,
    discover_directory_attachments,
    infer_document_format,
    parse_directory_document,
)

_ATTACHMENT_COUNTERS = (
    "attachment_links_discovered",
    "attachment_fetches_attempted",
    "attachment_cache_hits",
    "attachment_fetches_deferred",
    "attachment_documents_parsed",
    "attachment_documents_unsupported_or_invalid",
    "attachment_employer_candidates_extracted",
)
_SUPPORTED_REFERENCE_SUFFIXES = {".pdf", ".csv", ".tsv", ".json", ".xlsx"}
MAX_CIVIC_REFERENCE_CANDIDATES = 6
_STRONG_EMPLOYER_INTENT = re.compile(
    r"\b(?:major|top|largest|leading)\s+employers?\b|"
    r"\bemployers?\s+(?:directory|list|listing)\b|"
    r"\b(?:directory|list|listing)\s+of\s+employers?\b|"
    r"\b(?:business|company)\s+(?:directory|list|listing)\b",
    re.IGNORECASE,
)
_CIVIC_SELF_EMPLOYMENT = re.compile(
    r"\b(?:employment opportunities|government jobs?|municipal jobs?|"
    r"human resources|careers?)\b",
    re.IGNORECASE,
)
_EMPLOYER_LANDSCAPE_SIGNAL = re.compile(
    r"\b(?:local|regional|area|largest|major|top|leading)\s+"
    r"(?:employers?|companies?|business(?:es)?)\b|"
    r"\b(?:employer|business|company)\s+(?:directory|list|listing)\b|"
    r"\bcompany headquarters\b|\b(?:existing|target|key) industries\b|"
    r"\bworkforce (?:overview|profile|development)\b",
    re.IGNORECASE,
)


def _empty_attachment_counters() -> dict[str, int]:
    return {key: 0 for key in _ATTACHMENT_COUNTERS}


class _IntentAwareReferenceAdapter:
    """Preselect bounded civic references by employer-directory intent."""

    def __init__(
        self,
        delegate: Any,
        *,
        candidate_limit: int = MAX_CIVIC_REFERENCE_CANDIDATES,
    ) -> None:
        self.delegate = delegate
        self.candidate_limit = candidate_limit
        self.raw_result_count = 0
        self.selection_evidence: list[dict[str, Any]] = []

    async def search(self, query: str) -> Any:
        return await self.delegate.search(query)

    async def search_references(self, query: str) -> list[SearchResult]:
        method = getattr(self.delegate, "search_references", None)
        if method is None:
            method = self.delegate.search
        results = list(await method(query))
        self.raw_result_count = len(results)
        selected, evidence = _prioritize_civic_reference_results(
            results,
            reference_limit=self.candidate_limit,
        )
        self.selection_evidence = evidence
        return selected

    async def fetch_reference(self, url: str) -> Any:
        method = getattr(self.delegate, "fetch_reference", None)
        if method is None:
            return ""
        return await method(url)

    def reference_cache_status(self, url: str) -> str:
        method = getattr(self.delegate, "reference_cache_status", None)
        return method(url) if method is not None else "miss"

    def rank_civic_references(
        self,
        results: list[SearchResult],
    ) -> list[SearchResult]:
        return sorted(results, key=_reference_intent_rank)

    def is_civic_reference_eligible(self, result: SearchResult) -> bool:
        return _is_civic_reference_candidate(result)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.delegate, name)


class AttachmentAwareJobScoutDiscoveryLoop(LocationAwareJobScoutDiscoveryLoop):
    """Follow bounded civic directory attachments without treating names as companies."""

    def __init__(
        self,
        *args: Any,
        attachment_fetcher: PublicAttachmentFetcher | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        shared_fetcher = getattr(self.search_adapter, "fetcher", None)
        self.attachment_fetcher = attachment_fetcher or PublicAttachmentFetcher(
            self.coordinator.search_cache,
            fetcher=shared_fetcher,
        )
        self._attachment_cycle_totals: dict[str, int] | None = None

    async def prepare(self, run_id: str) -> dict[str, object]:
        prepared = await super().prepare(run_id)
        persisted = _persist_attachment_coverage(self.learning, run_id)
        return {
            **prepared,
            "coverage": {**dict(prepared.get("coverage") or {}), **persisted},
        }

    async def cycle(
        self,
        run_id: str,
        cycle: int,
        request_limit: int | None = None,
    ):  # type: ignore[no-untyped-def]
        self._attachment_cycle_totals = _empty_attachment_counters()
        try:
            summary = await super().cycle(run_id, cycle, request_limit)
            totals = dict(self._attachment_cycle_totals)
        finally:
            self._attachment_cycle_totals = None
        persisted = _persist_attachment_coverage(
            self.learning,
            run_id,
            increments=totals,
        )
        return replace(
            summary,
            coverage={**summary.coverage, **persisted},
            yield_metrics={**summary.yield_metrics, **totals},
        )

    async def _execute_public_search(
        self,
        strategy: DiscoveryStrategySnapshot,
        allowance: _RequestAllowance | None = None,
    ) -> tuple[StrategyOutcome, int, list[str]]:
        allowance = allowance or _RequestAllowance()
        start_requests = allowance.used
        is_local_employer = (
            strategy.dimensions.get("hypothesis_family") == "local_employer"
        )
        original_adapter = self.search_adapter
        reference_adapter: _IntentAwareReferenceAdapter | None = None
        if is_local_employer:
            reference_adapter = _IntentAwareReferenceAdapter(original_adapter)
            self.search_adapter = reference_adapter
        try:
            outcome, _base_requests, warnings = await super()._execute_public_search(
                strategy,
                allowance,
            )
        finally:
            self.search_adapter = original_adapter
        if not is_local_employer:
            return outcome, allowance.used - start_requests, warnings

        stages = dict(outcome.detail.get("stages") or {})
        if reference_adapter is not None:
            stages["search_results_returned"] = reference_adapter.raw_result_count
            stages["reference_selection_evidence"] = reference_adapter.selection_evidence
        references = stages.get("employer_reference_evidence")
        if not isinstance(references, list):
            detail = {**outcome.detail, "stages": stages}
            return (
                replace(outcome, detail=detail),
                allowance.used - start_requests,
                warnings,
            )

        metrics = _empty_attachment_counters()
        attachment_evidence: list[dict[str, Any]] = []
        known_strategy_ids = {item.id for item in self.learning.list_strategies()}
        created_hypotheses = 0
        for reference in references:
            if not isinstance(reference, dict) or reference.get("status") != "inspected":
                continue
            parent_url = str(reference.get("url") or "").strip()
            if not parent_url:
                continue
            parent = await _cached_parent_document(self.search_adapter, parent_url)
            if parent is None:
                continue
            format_name = infer_document_format(parent.url, parent.content_type)
            if format_name in {"pdf", "csv", "tsv", "json", "xlsx"}:
                direct = AttachmentLink(
                    parent_url=parent.url,
                    url=parent.url,
                    link_text="",
                    hinted_content_type=parent.content_type,
                    format_hint=format_name,
                )
                direct_created = await self._process_attachment_links(
                    strategy,
                    parent,
                    [direct],
                    allowance,
                    metrics,
                    attachment_evidence,
                    known_strategy_ids,
                    direct_reference=True,
                )
                created_hypotheses += direct_created
                continue
            links = discover_directory_attachments(parent.url, parent.text)
            metrics["attachment_links_discovered"] += len(links)
            created_hypotheses += await self._process_attachment_links(
                strategy,
                parent,
                links,
                allowance,
                metrics,
                attachment_evidence,
                known_strategy_ids,
            )

        stages.update(metrics)
        stages["employer_candidates_discovered"] = int(
            stages.get("employer_candidates_discovered", 0)
        ) + created_hypotheses
        stages["attachment_reference_evidence"] = attachment_evidence
        detail = {**outcome.detail, "stages": stages}
        if self._attachment_cycle_totals is not None:
            for key, value in metrics.items():
                self._attachment_cycle_totals[key] += value
        return (
            replace(outcome, detail=detail),
            allowance.used - start_requests,
            warnings,
        )

    async def _process_attachment_links(
        self,
        strategy: DiscoveryStrategySnapshot,
        parent: ReferenceDocument,
        links: list[AttachmentLink],
        allowance: _RequestAllowance,
        metrics: dict[str, int],
        evidence: list[dict[str, Any]],
        known_strategy_ids: set[str],
        *,
        direct_reference: bool = False,
    ) -> int:
        network_fetches = 0
        documents_processed = 0
        candidates_remaining = MAX_ATTACHMENT_CANDIDATES_PER_REFERENCE
        created = 0
        for link in links:
            if documents_processed >= MAX_ATTACHMENT_DOCUMENTS_PER_REFERENCE:
                break
            if not link.supported:
                metrics["attachment_documents_unsupported_or_invalid"] += 1
                evidence.append(
                    _attachment_evidence(
                        link,
                        status="unsupported",
                        content_type=link.hinted_content_type,
                        extraction_method="unsupported",
                    )
                )
                continue

            if direct_reference and link.format_hint in {"csv", "tsv", "json"}:
                document = DirectoryDocument(
                    url=parent.url,
                    content=parent.text.encode("utf-8", errors="replace"),
                    text=parent.text,
                    content_type=parent.content_type,
                    cache_status=parent.cache_status,
                )
                cache_status = parent.cache_status
            else:
                cache_status = self.attachment_fetcher.cache_status(link.url)
                if cache_status == "retry_deferred":
                    metrics["attachment_fetches_deferred"] += 1
                    evidence.append(
                        _attachment_evidence(link, status="retry_deferred")
                    )
                    continue
                if cache_status == "invalid":
                    metrics["attachment_documents_unsupported_or_invalid"] += 1
                    evidence.append(
                        _attachment_evidence(link, status="cached_invalid")
                    )
                    continue
                if cache_status == "miss":
                    if (
                        network_fetches >= MAX_ATTACHMENT_FETCHES_PER_REFERENCE
                        or allowance.exhausted
                    ):
                        evidence.append(
                            _attachment_evidence(link, status="budget_or_fetch_cap")
                        )
                        continue
                    try:
                        allowance.reserve()
                    except _RequestAllowanceExhausted:
                        evidence.append(
                            _attachment_evidence(link, status="budget_exhausted")
                        )
                        continue
                    network_fetches += 1
                    metrics["attachment_fetches_attempted"] += 1
                elif cache_status == "hit":
                    metrics["attachment_cache_hits"] += 1
                try:
                    document = await self.attachment_fetcher.fetch(link.url)
                except SearchChallengeError:
                    metrics["attachment_fetches_deferred"] += 1
                    evidence.append(
                        _attachment_evidence(link, status="retry_deferred")
                    )
                    continue
                except AttachmentDocumentError as error:
                    metrics["attachment_documents_unsupported_or_invalid"] += 1
                    evidence.append(
                        _attachment_evidence(
                            link,
                            status="invalid",
                            extraction_method="invalid",
                            detail=str(error),
                        )
                    )
                    continue

            documents_processed += 1
            parsed = parse_directory_document(
                document,
                candidate_limit=candidates_remaining,
            )
            if parsed.status == "parsed":
                metrics["attachment_documents_parsed"] += 1
            else:
                metrics["attachment_documents_unsupported_or_invalid"] += 1
                if cache_status in {"hit", "miss"} and not direct_reference:
                    self.attachment_fetcher.mark_invalid(link.url, parsed.detail or parsed.status)
            candidates = list(parsed.candidates)[:candidates_remaining]
            candidates_remaining -= len(candidates)
            metrics["attachment_employer_candidates_extracted"] += len(candidates)
            evidence.append(
                _attachment_evidence(
                    link,
                    status=parsed.status,
                    final_url=document.url,
                    content_type=document.content_type,
                    extraction_method=parsed.extraction_method,
                    candidate_count=len(candidates),
                    cache_status=cache_status,
                    units_inspected=parsed.units_inspected,
                    detail=parsed.detail,
                )
            )
            for candidate in candidates:
                snapshot = self.learning.ensure_strategy(
                    {
                        "kind": "public_search",
                        "hypothesis_family": "local_employer_deepen",
                        "anchor": candidate,
                        "location": strategy.dimensions.get("location", ""),
                        "source_domain": "web",
                        "source_path": "broad_web",
                        "employer_evidence_authority": "civic_attachment",
                        "employer_evidence_parent_url": link.parent_url,
                        "employer_evidence_url": link.url,
                        "employer_evidence_final_url": document.url,
                        "employer_evidence_link_text": link.link_text,
                        "employer_evidence_content_type": document.content_type,
                        "employer_evidence_extraction_method": parsed.extraction_method,
                        "market_provenance": strategy.dimensions.get(
                            "market_provenance", ""
                        ),
                        "market_kind": strategy.dimensions.get("market_kind", ""),
                        "market_distance_miles": strategy.dimensions.get(
                            "market_distance_miles", ""
                        ),
                        "market_rank": strategy.dimensions.get("market_rank", ""),
                    },
                    origin="public_employer_attachment_evidence",
                )
                if snapshot.id not in known_strategy_ids:
                    known_strategy_ids.add(snapshot.id)
                    created += 1
            if candidates_remaining <= 0:
                break
        return created


def _prioritize_civic_reference_results(
    results: list[SearchResult],
    *,
    reference_limit: int = 2,
) -> tuple[list[SearchResult], list[dict[str, Any]]]:
    """Keep only the strongest bounded civic references while preserving other results."""

    civic = [
        item
        for item in results
        if item.classification is UrlClassification.OTHER and _is_civic_authority(item)
    ]
    eligible = [item for item in civic if _is_civic_reference_candidate(item)]
    rejected = [item for item in civic if item not in eligible]
    ranked = sorted(eligible, key=_reference_intent_rank)
    selected = ranked[: max(reference_limit, 0)]
    civic_ids = {id(item) for item in civic}
    non_civic = [item for item in results if id(item) not in civic_ids]
    selected_ids = {id(item) for item in selected}
    evidence: list[dict[str, Any]] = []
    for item in [*ranked, *rejected][:8]:
        intent_tier, authority_tier, _url = _reference_intent_rank(item)
        is_eligible = item in eligible
        evidence.append(
            {
                "url": item.url,
                "title": item.title[:300],
                "selected": id(item) in selected_ids,
                "eligible": is_eligible,
                "rejection_reason": "" if is_eligible else "civic_self_employment",
                "intent_tier": intent_tier,
                "authority_tier": authority_tier,
                "supported_document": _supported_reference_document(item.url),
            }
        )
    return [*selected, *rejected, *non_civic], evidence


def _reference_intent_rank(result: SearchResult) -> tuple[int, int, str]:
    url = str(result.url)
    parsed = urlsplit(url)
    domain = (parsed.hostname or "").casefold()
    compact_domain = re.sub(r"[^a-z]", "", domain)
    evidence_text = " ".join(
        (
            str(result.title),
            str(result.snippet),
            parsed.path.replace("-", " ").replace("_", " "),
        )
    ).casefold()
    explicit_subject = bool(
        re.search(r"\b(?:employers?|companies?|business(?:es)?)\b", evidence_text)
    )
    if _STRONG_EMPLOYER_INTENT.search(evidence_text):
        intent_tier = 0
    elif _supported_reference_document(url) and explicit_subject:
        intent_tier = 1
    elif explicit_subject or "workforce" in evidence_text:
        intent_tier = 2
    else:
        intent_tier = 3

    if domain.endswith(".gov"):
        authority_tier = 0
    elif any(
        marker in compact_domain
        for marker in ("economicdevelopment", "chamber", "partnership")
    ):
        authority_tier = 1
    elif domain.endswith(".org") or "council" in compact_domain:
        authority_tier = 2
    else:
        authority_tier = 3
    return intent_tier, authority_tier, url.casefold()


def _is_civic_reference_candidate(result: SearchResult) -> bool:
    if not _is_civic_authority(result):
        return False
    evidence_text = _reference_evidence_text(result)
    return not (
        _CIVIC_SELF_EMPLOYMENT.search(evidence_text)
        and not _EMPLOYER_LANDSCAPE_SIGNAL.search(evidence_text)
    )


def _is_civic_authority(result: SearchResult) -> bool:
    domain = (urlsplit(str(result.url)).hostname or "").casefold()
    compact = re.sub(r"[^a-z]", "", domain)
    return domain.endswith((".gov", ".org")) or any(
        marker in compact
        for marker in ("economicdevelopment", "chamber", "partnership", "council")
    )


def _reference_evidence_text(result: SearchResult) -> str:
    parsed = urlsplit(str(result.url))
    return " ".join(
        (
            str(result.title),
            str(result.snippet),
            parsed.path.replace("-", " ").replace("_", " "),
        )
    ).casefold()


def _supported_reference_document(url: str) -> bool:
    path = urlsplit(url).path.casefold()
    return any(path.endswith(suffix) for suffix in _SUPPORTED_REFERENCE_SUFFIXES)


def _attachment_evidence(
    link: AttachmentLink,
    *,
    status: str,
    final_url: str = "",
    content_type: str = "",
    extraction_method: str = "",
    candidate_count: int = 0,
    cache_status: str = "",
    units_inspected: int = 0,
    detail: str = "",
) -> dict[str, Any]:
    return {
        "parent_page_url": link.parent_url,
        "attachment_url": link.url,
        "final_url": final_url,
        "link_text": link.link_text,
        "content_type": content_type,
        "extraction_method": extraction_method,
        "candidate_count": candidate_count,
        "cache_status": cache_status,
        "status": status,
        "units_inspected": units_inspected,
        "detail": detail[:500],
    }


async def _cached_parent_document(adapter: Any, url: str) -> ReferenceDocument | None:
    fetch_reference = getattr(adapter, "fetch_reference", None)
    cache_status_method = getattr(adapter, "reference_cache_status", None)
    if fetch_reference is None or cache_status_method is None:
        return None
    if cache_status_method(url) != "hit":
        return None
    try:
        fetched = await fetch_reference(url)
    except (RuntimeError, SearchChallengeError):
        return None
    if isinstance(fetched, ReferenceDocument):
        return fetched
    return ReferenceDocument(
        url=url,
        text=str(fetched),
        content_type="text/html",
        cache_status="unavailable",
    )


def _persist_attachment_coverage(
    learning: JobScoutDiscoveryRepository,
    run_id: str,
    *,
    increments: dict[str, int] | None = None,
) -> dict[str, int]:
    """Persist extension counters while core coverage remains backward compatible."""

    current_time = datetime.now(UTC)
    with learning.database.session() as session:
        model = session.get(DiscoverySessionModel, run_id)
        if model is None:
            return _empty_attachment_counters()
        coverage = dict(model.coverage or {})
        for key in _ATTACHMENT_COUNTERS:
            coverage.setdefault(key, 0)
            coverage[key] = int(coverage[key]) + int((increments or {}).get(key, 0))
        model.coverage = coverage
        model.updated_at = current_time
        session.flush()
        return {key: int(coverage[key]) for key in _ATTACHMENT_COUNTERS}
