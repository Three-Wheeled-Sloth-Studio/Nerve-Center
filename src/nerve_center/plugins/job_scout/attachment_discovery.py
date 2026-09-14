"""Attachment-aware extension for location-sensitive Job Scout discovery."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from nerve_center.discovery.search import ReferenceDocument, SearchChallengeError
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


def _empty_attachment_counters() -> dict[str, int]:
    return {key: 0 for key in _ATTACHMENT_COUNTERS}


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
        outcome, _base_requests, warnings = await super()._execute_public_search(
            strategy,
            allowance,
        )
        if strategy.dimensions.get("hypothesis_family") != "local_employer":
            return outcome, allowance.used - start_requests, warnings

        stages = dict(outcome.detail.get("stages") or {})
        references = stages.get("employer_reference_evidence")
        if not isinstance(references, list):
            return outcome, allowance.used - start_requests, warnings

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
