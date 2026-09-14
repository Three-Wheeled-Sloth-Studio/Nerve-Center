"""Iterative, company-first Job Scout market discovery orchestration."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from html.parser import HTMLParser
from typing import Any, Protocol
from urllib.parse import urljoin, urlsplit
from zipfile import BadZipFile

import httpx

from nerve_center.config import Settings
from nerve_center.discovery.connectors.sitemap import SitemapConnector
from nerve_center.discovery.models import (
    AcquisitionClass,
    Company,
    DiscoverySource,
    SourceKind,
)
from nerve_center.discovery.normalization import canonicalize_url, stable_source_id
from nerve_center.discovery.search import (
    PublicWebSearchAdapter,
    ReferenceDocument,
    SearchAdapter,
    SearchChallengeError,
    UrlClassification,
)
from nerve_center.discovery.service import DiscoveryService
from nerve_center.persistence.discovery import (
    CompanyRepository,
    DiscoverySourceRepository,
    JobOpeningRepository,
)
from nerve_center.plugins.job_scout.configuration import JobScoutCoordinator
from nerve_center.plugins.job_scout.discovery_learning import (
    DiscoveryStrategySnapshot,
    JobScoutDiscoveryRepository,
    StrategyOutcome,
)
from nerve_center.plugins.job_scout.market import GazetteerMarketExpander, MarketAlias
from nerve_center.plugins.job_scout.settings import clean_list


class MarketExpander(Protocol):
    async def expand(self, locations: list[str], **kwargs: Any) -> list[MarketAlias]: ...


class SurfaceResolver(Protocol):
    async def resolve(self, company: Company) -> list[str]: ...


@dataclass(frozen=True, slots=True)
class DiscoveryCycleSummary:
    run_id: str
    cycle: int
    strategies_attempted: int
    request_count: int
    useful_yield: int
    openings_found: int
    needs_reflection: bool
    strategies_exhausted: bool
    warnings: list[str]
    coverage: dict[str, Any]
    yield_metrics: dict[str, int]


class _RequestAllowance:
    """Reserve a bounded cycle's outbound calls before network work begins."""

    def __init__(self, limit: int | None = None) -> None:
        if limit is not None and limit < 0:
            raise ValueError("request limit cannot be negative")
        self.limit = limit
        self.used = 0

    @property
    def exhausted(self) -> bool:
        return self.limit is not None and self.used >= self.limit

    def reserve(self) -> None:
        if self.exhausted:
            raise _RequestAllowanceExhausted
        self.used += 1


class _RequestAllowanceExhausted(RuntimeError):
    pass


MAX_REFERENCE_NETWORK_FETCH_ATTEMPTS = 3


class PublicCareerSurfaceResolver:
    """Inspect one public employer career page for ATS and sitemap surfaces."""

    def __init__(self, discovery: DiscoveryService) -> None:
        self.discovery = discovery

    async def resolve(self, company: Company) -> list[str]:
        if not company.career_url:
            return []
        fetcher = self.discovery.fetcher_factory()
        response = await fetcher.get(company.career_url)
        if response.challenged or response.throttled or response.status_code >= 400:
            return []
        parser = _CareerLinkParser(company.career_url)
        parser.feed(response.text)
        parser.close()
        links = parser.links
        if not any("sitemap" in item.casefold() for item in links):
            links.append(urljoin(company.career_url, "/sitemap.xml"))
        return clean_list(links)[:12]


class _CareerLinkParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        href = values.get("href")
        if not href:
            return
        absolute = canonicalize_url(urljoin(self.base_url, href))
        lowered = absolute.casefold()
        rel = (values.get("rel") or "").casefold()
        if (
            "greenhouse.io" in lowered
            or "lever.co" in lowered
            or "ashbyhq.com" in lowered
            or "sitemap" in lowered
            or (tag == "link" and "sitemap" in rel)
        ):
            self.links.append(absolute)


class _EmployerLandscapeParser(HTMLParser):
    """Capture heading structure from a public employer-landscape page."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.headings: list[tuple[int, str]] = []
        self.items: list[tuple[str, int | None, str]] = []
        self._level: int | None = None
        self._capture_tag: str | None = None
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, _attrs: list[tuple[str, str | None]]) -> None:
        if len(tag) == 2 and tag.startswith("h") and tag[1].isdigit():
            self._level = int(tag[1])
            self._capture_tag = tag
            self._parts = []
        elif tag in {"li", "td"} and self._capture_tag is None:
            self._capture_tag = tag
            self._parts = []

    def handle_data(self, data: str) -> None:
        if self._capture_tag is not None:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._capture_tag is None or tag != self._capture_tag:
            return
        text = " ".join("".join(self._parts).split())
        if text:
            self.items.append((tag, self._level, text))
            if self._level is not None:
                self.headings.append((self._level, text))
        self._level = None
        self._capture_tag = None
        self._parts = []


class JobScoutDiscoveryLoop:
    """Run one resumable discovery double-diamond inside a manager-owned session."""

    def __init__(
        self,
        settings: Settings,
        coordinator: JobScoutCoordinator,
        discovery: DiscoveryService,
        companies: CompanyRepository,
        sources: DiscoverySourceRepository,
        jobs: JobOpeningRepository,
        learning: JobScoutDiscoveryRepository,
        *,
        market: MarketExpander | None = None,
        search_adapter: SearchAdapter | None = None,
        surface_resolver: SurfaceResolver | None = None,
        exploration_floor: float = 0.25,
        strategies_per_cycle: int = 4,
        results_per_strategy: int = 6,
    ) -> None:
        self.settings = settings
        self.coordinator = coordinator
        self.discovery = discovery
        self.companies = companies
        self.sources = sources
        self.jobs = jobs
        self.learning = learning
        self.market = market or GazetteerMarketExpander(settings)
        self.search_adapter = search_adapter or PublicWebSearchAdapter(
            coordinator.search_cache,
            max_results=25,
        )
        self.surface_resolver = surface_resolver or PublicCareerSurfaceResolver(discovery)
        self.exploration_floor = exploration_floor
        self.strategies_per_cycle = strategies_per_cycle
        self.results_per_strategy = results_per_strategy

    async def prepare(self, run_id: str) -> dict[str, Any]:
        configuration = self.coordinator.save_configuration(self.coordinator.store.load())
        keyword_summary = self.coordinator._discover_keywords(configuration)
        warnings: list[str] = []
        try:
            aliases = await self.market.expand(configuration.locations)
        except (httpx.HTTPError, OSError, ValueError, BadZipFile) as error:
            aliases = [
                MarketAlias(location, "configured", 0.0, "configured_starting_location")
                for location in configuration.locations
            ]
            warnings.append(f"Local-market reference expansion unavailable: {error}")
        locations = clean_list([item.label for item in aliases]) or [""]
        anchors = clean_list([*configuration.target_titles, *keyword_summary.keywords])[:14]
        if not anchors:
            anchors = ["product management"]
        before = len(self.learning.list_strategies())
        self._seed_search_strategies(
            anchors,
            locations,
            configuration.public_job_boards,
        )
        self._seed_market_strategies(aliases)
        self._seed_known_company_strategies()
        self._seed_due_source_strategies()
        after = len(self.learning.list_strategies())
        feedback_applied = self.learning.sync_application_feedback()
        try:
            prior = self.learning.session(run_id)
            prior_cycle = prior.cycle
            prior_no_yield = prior.no_yield_cycles
        except KeyError:
            prior_cycle = 0
            prior_no_yield = 0
        session = self.learning.update_session(
            run_id,
            phase="expand",
            cycle=prior_cycle,
            no_yield_cycles=prior_no_yield,
            increments={"strategy_changes": max(after - before, 0)},
            warnings=warnings,
        )
        return {
            "strategies_available": after,
            "strategies_added": max(after - before, 0),
            "location_aliases": len(locations),
            "feedback_events_applied": feedback_applied,
            "warnings": warnings,
            "coverage": session.coverage,
        }

    async def cycle(
        self,
        run_id: str,
        cycle: int,
        request_limit: int | None = None,
    ) -> DiscoveryCycleSummary:
        # New employer surfaces are work, even when the previous reflection was empty.
        self._seed_known_company_strategies()
        self._seed_due_source_strategies()
        board_domains = {
            _clean_domain(item)
            for item in self.coordinator.store.load().public_job_boards
        }
        excluded_company_ids = {
            item.id for item in self.companies.list() if item.domain in board_domains
        }
        excluded_source_ids = {
            item.id
            for item in self.sources.list()
            if not _is_employer_source(item) or item.company_id in excluded_company_ids
        }
        due_ids = {item.id for item in self.sources.list_due()}
        excluded_source_ids.update(
            item.id for item in self.sources.list() if item.id not in due_ids
        )
        selected = self.learning.select_strategies(
            run_id,
            limit=self.strategies_per_cycle,
            exploration_floor=self.exploration_floor,
            excluded_company_ids=excluded_company_ids,
            excluded_source_ids=excluded_source_ids,
            revisit_after_seconds=86400,
        )
        if not selected:
            session = self.learning.update_session(run_id, phase="reflect", cycle=cycle)
            return DiscoveryCycleSummary(
                run_id=run_id,
                cycle=cycle,
                strategies_attempted=0,
                request_count=0,
                useful_yield=0,
                openings_found=0,
                needs_reflection=True,
                strategies_exhausted=True,
                warnings=[],
                coverage=session.coverage,
                yield_metrics={},
            )
        allowance = _RequestAllowance(request_limit)
        request_count = 0
        useful_yield = 0
        openings_found = 0
        warnings: list[str] = []
        increments = {
            "strategies_attempted": 0,
            "public_searches_executed": 0,
            "search_requests_completed": 0,
            "search_requests_failed": 0,
            "search_results_returned": 0,
            "search_results_eligible": 0,
            "search_sources_registered": 0,
            "source_scans_attempted": 0,
            "source_scans_completed": 0,
            "regional_aliases_discovered": 0,
            "reference_pages_inspected": 0,
            "reference_cache_hits": 0,
            "reference_fetches_deferred": 0,
            "reference_network_fetches_attempted": 0,
            "employer_candidates_discovered": 0,
            "results_examined": 0,
            "companies_discovered": 0,
            "career_sources_resolved": 0,
            "known_company_sources_revisited": 0,
            "postings_inspected": 0,
            "opportunities_retained": 0,
        }
        for strategy in selected:
            if allowance.exhausted:
                break
            source_ids_before = self._career_source_ids()
            job_ids_before = {item.id for item in self.jobs.list(active_only=False)}
            outcome, used_requests, strategy_warnings = await self._execute_strategy(
                strategy,
                allowance,
            )
            # Successful revisits are valuable coverage, but only newly durable
            # sources and openings are discovery yield. Otherwise cached/repeated
            # pages continually promote a strategy and prevent reflection.
            outcome = replace(
                outcome,
                career_sources_resolved=len(
                    self._career_source_ids() - source_ids_before
                ),
                opportunities_retained=len(
                    {item.id for item in self.jobs.list(active_only=False)} - job_ids_before
                ),
            )
            self.learning.record_attempt(run_id, cycle, strategy.id, "deepen", outcome)
            request_count += used_requests
            useful_yield += outcome.useful_yield
            openings_found += outcome.opportunities_retained
            warnings.extend(strategy_warnings)
            increments["strategies_attempted"] += 1
            increments["results_examined"] += outcome.results_examined
            increments["companies_discovered"] += outcome.companies_discovered
            increments["career_sources_resolved"] += outcome.career_sources_resolved
            increments["postings_inspected"] += outcome.postings_inspected
            increments["opportunities_retained"] += outcome.opportunities_retained
            stages = outcome.detail.get("stages", {})
            if isinstance(stages, dict):
                for key in (
                    "search_requests_completed",
                    "search_requests_failed",
                    "search_results_returned",
                    "search_results_eligible",
                    "search_sources_registered",
                    "source_scans_attempted",
                    "source_scans_completed",
                    "regional_aliases_discovered",
                    "reference_pages_inspected",
                    "reference_cache_hits",
                    "reference_fetches_deferred",
                    "reference_network_fetches_attempted",
                    "employer_candidates_discovered",
                ):
                    increments[key] += max(int(stages.get(key, 0)), 0)
            if strategy.dimensions.get("kind") == "public_search":
                increments["public_searches_executed"] += 1
            if strategy.dimensions.get("kind") in {"company_revisit", "source_revisit"}:
                increments["known_company_sources_revisited"] += 1
        previous = self.learning.session(run_id)
        no_yield = previous.no_yield_cycles + 1 if useful_yield == 0 else 0
        session = self.learning.update_session(
            run_id,
            phase="converge" if useful_yield else "reflect",
            cycle=cycle,
            no_yield_cycles=no_yield,
            increments=increments,
            warnings=warnings,
        )
        return DiscoveryCycleSummary(
            run_id=run_id,
            cycle=cycle,
            strategies_attempted=increments["strategies_attempted"],
            request_count=request_count,
            useful_yield=useful_yield,
            openings_found=openings_found,
            needs_reflection=no_yield >= 2,
            strategies_exhausted=False,
            warnings=clean_list(warnings),
            coverage=session.coverage,
            yield_metrics=increments,
        )

    def deterministic_reflection(self, run_id: str, cycle: int) -> dict[str, Any]:
        existing_ids = {item.id for item in self.learning.list_strategies()}
        configuration = self.coordinator.store.load()
        keywords = self.coordinator._discover_keywords(configuration).keywords
        hypotheses: list[tuple[str, dict[str, str]]] = []
        for keyword in keywords[8:14]:
            hypotheses.append(
                (
                    (
                        "Try a resume-derived adjacent term not used in the first search wave: "
                        f"{keyword}"
                    ),
                    {"kind": "public_search", "anchor": keyword, "source_domain": "web"},
                )
            )
        for company in self.companies.list():
            company_sources = [
                item for item in self.sources.list() if item.company_id == company.id
            ]
            if company_sources:
                continue
            hypotheses.append(
                (
                    f"Deepen a known employer that has no durable career source: {company.domain}",
                    {"kind": "company_revisit", "company_id": company.id},
                )
            )
        created = 0
        for hypothesis, dimensions in hypotheses[:8]:
            strategy = self.learning.ensure_strategy(
                dimensions,
                origin="deterministic_reflection",
            )
            if strategy.id in existing_ids:
                continue
            existing_ids.add(strategy.id)
            created += 1
            self.learning.record_reflection_hypothesis(
                run_id,
                cycle,
                origin="deterministic",
                hypothesis=hypothesis,
                dimensions=strategy.dimensions,
                strategy_id=strategy.id,
            )
        if created:
            self.learning.update_session(
                run_id,
                phase="expand",
                increments={"strategy_changes": created},
            )
        return {
            "new_strategies": created,
            "llm_recommended": created == 0,
        }

    def reflection_work_request(self, run_id: str, cycle: int) -> dict[str, Any]:
        session = self.learning.session(run_id)
        strategies = self.learning.list_strategies()
        evidence = {
            "coverage": session.coverage,
            "strategies": [
                {
                    "dimensions": item.dimensions,
                    "weight": round(item.learned_weight, 3),
                    "attempts": item.attempts,
                    "retained": item.opportunities_retained,
                    "companies": item.companies_discovered,
                    "sources": item.career_sources_resolved,
                    "influence": item.influence,
                }
                for item in strategies[:30]
            ],
        }
        return {
            "task_id": "job_scout.discovery.reflect",
            "work_class": "llm",
            "payload": {
                "system_prompt": (
                    "You are a bounded job-market discovery strategist. Suggest search paths the "
                    "deterministic Job Scout has not already tried. Optimize discovery recall, not "
                    "job ranking. Do not suggest authenticated LinkedIn crawling, CAPTCHA bypass, "
                    "outreach, applications, or person enrichment."
                ),
                "user_prompt": (
                    "Review this coverage and strategy evidence and propose up to six materially "
                    f"different public discovery strategies. Evidence: {evidence}"
                ),
            },
            "provenance": {
                "module": "job_scout",
                "purpose": "diminishing_return_reflection",
                "run_id": run_id,
                "cycle": cycle,
            },
            "output_contract": _reflection_schema(),
            "requirements": {"contract_version": "job-scout-discovery-reflection-v1"},
            "idempotency_key": f"job-scout-reflect:{run_id}:{cycle}",
            "task_priority": 25,
            "max_retries": 1,
        }

    def apply_reflection_result(self, request_id: str, value: dict[str, Any]) -> int:
        request = self.learning.reflection_request(request_id)
        if request is None or request["status"] == "applied":
            return 0
        created = 0
        known_ids = {item.id for item in self.learning.list_strategies()}
        strategies = value.get("strategies", [])
        if not isinstance(strategies, list):
            raise ValueError("reflection result strategies must be a list")
        for item in strategies[:6]:
            if not isinstance(item, dict):
                continue
            dimensions = {
                "kind": "public_search",
                "anchor": str(item.get("anchor") or "").strip(),
                "location": str(item.get("location") or "").strip(),
                "source_domain": str(item.get("source_domain") or "web").strip(),
                "employer_archetype": str(item.get("employer_archetype") or "").strip(),
            }
            strategy = self.learning.ensure_strategy(dimensions, origin="llm_reflection")
            if strategy.id in known_ids:
                continue
            known_ids.add(strategy.id)
            created += 1
            self.learning.record_reflection_hypothesis(
                str(request["run_id"]),
                int(request["cycle"]),
                origin="llm",
                hypothesis=str(item.get("rationale") or "LLM-proposed unexplored search path"),
                dimensions=strategy.dimensions,
                strategy_id=strategy.id,
            )
        if created:
            self.learning.update_session(
                str(request["run_id"]),
                phase="expand",
                increments={"strategy_changes": created},
            )
        self.learning.mark_reflection_applied(request_id)
        return created

    def summary(self, run_id: str) -> dict[str, Any]:
        session = self.learning.session(run_id)
        return {
            "phase": session.phase,
            "cycle": session.cycle,
            "no_yield_cycles": session.no_yield_cycles,
            **session.coverage,
        }

    def _seed_search_strategies(
        self,
        anchors: list[str],
        locations: list[str],
        boards: list[str],
    ) -> None:
        domains = clean_list([_clean_domain(item) for item in boards if _clean_domain(item)])
        paths = ["web", *domains]
        seeded = 0
        for location in locations[:12]:
            for source_domain in paths:
                for anchor in anchors:
                    self.learning.ensure_strategy(
                        {
                            "kind": "public_search",
                            "anchor": anchor,
                            "location": location,
                            "source_domain": source_domain,
                        },
                        origin="profile_and_market",
                    )
                    seeded += 1
                    if seeded >= 96:
                        return

    def _seed_market_strategies(self, aliases: list[MarketAlias]) -> None:
        """Optional market-evidence strategies supplied by richer loop layers."""

    def _seed_known_company_strategies(self) -> None:
        board_domains = {
            _clean_domain(item)
            for item in self.coordinator.store.load().public_job_boards
        }
        for company in self.companies.list():
            if company.domain in board_domains:
                continue
            self.learning.ensure_strategy(
                {"kind": "company_revisit", "company_id": company.id},
                origin="known_company",
            )

    def _seed_due_source_strategies(self) -> None:
        for source in self.sources.list_due():
            if not _is_employer_source(source):
                continue
            self.learning.ensure_strategy(
                {"kind": "source_revisit", "source_id": source.id},
                origin="known_source",
            )

    async def _execute_strategy(
        self,
        strategy: DiscoveryStrategySnapshot,
        allowance: _RequestAllowance | None = None,
    ) -> tuple[StrategyOutcome, int, list[str]]:
        allowance = allowance or _RequestAllowance()
        kind = strategy.dimensions.get("kind")
        if kind == "public_search":
            return await self._execute_public_search(strategy, allowance)
        if kind == "company_revisit":
            return await self._execute_company_revisit(strategy, allowance)
        if kind == "source_revisit":
            return await self._execute_source_revisit(strategy, allowance)
        return StrategyOutcome(status="failed", failed=1), 0, [f"Unknown strategy kind: {kind}"]

    async def _execute_public_search(
        self,
        strategy: DiscoveryStrategySnapshot,
        allowance: _RequestAllowance | None = None,
    ) -> tuple[StrategyOutcome, int, list[str]]:
        allowance = allowance or _RequestAllowance()
        start_requests = allowance.used
        query = _strategy_query(strategy)
        warnings: list[str] = []
        try:
            allowance.reserve()
            search = self.search_adapter.search
            if strategy.dimensions.get("hypothesis_family") in {
                "local_employer",
                "regional_alias_probe",
            }:
                search = getattr(self.search_adapter, "search_references", search)
            results = await search(query)
        except _RequestAllowanceExhausted:
            return StrategyOutcome(status="budget_exhausted"), 0, []
        except SearchChallengeError as error:
            return (
                StrategyOutcome(
                    status="challenged",
                    challenged=1,
                    detail={
                        "query": query,
                        "stages": {"search_requests_failed": 1},
                    },
                ),
                allowance.used - start_requests,
                [str(error)],
            )
        except RuntimeError as error:
            return (
                StrategyOutcome(
                    status="failed",
                    failed=1,
                    detail={
                        "query": query,
                        "stages": {"search_requests_failed": 1},
                    },
                ),
                allowance.used - start_requests,
                [str(error)],
            )
        if strategy.dimensions.get("hypothesis_family") == "regional_alias_probe":
            inspected_results = results[: self.results_per_strategy]
            evidence = _extract_regional_alias_evidence(
                inspected_results,
                anchor=strategy.dimensions.get("anchor", ""),
            )
            created = 0
            target_titles = self.coordinator.store.load().target_titles[:2]
            for item in evidence:
                for title in target_titles or ["product management"]:
                    before = len(self.learning.list_strategies())
                    self.learning.ensure_strategy(
                        {
                            "kind": "public_search",
                            "hypothesis_family": "regional_alias",
                            "anchor": title,
                            "location": item["alias"],
                            "source_domain": "web",
                            "source_path": "broad_web",
                            "alias_provenance_url": item["url"],
                        },
                        origin="public_regional_alias_evidence",
                    )
                    created += int(len(self.learning.list_strategies()) > before)
            return (
                StrategyOutcome(
                    results_examined=len(inspected_results),
                    detail={
                        "query": query,
                        "regional_alias_evidence": evidence,
                        "stages": {
                            "search_requests_completed": 1,
                            "search_results_returned": len(results),
                            "regional_aliases_discovered": len(evidence),
                            "strategies_created": created,
                        },
                    },
                ),
                allowance.used - start_requests,
                warnings,
            )
        companies_before = {item.id for item in self.companies.list()}
        companies_seen: set[str] = set()
        sources_seen: set[str] = set()
        postings = 0
        retained = 0
        configuration = self.coordinator.store.load()
        result_limit = (
            max(self.results_per_strategy, 12)
            if strategy.dimensions.get("hypothesis_family") == "local_employer"
            else self.results_per_strategy
        )
        inspected_results = results[:result_limit]
        eligible_results = 0
        registered_sources = 0
        scans_attempted = 0
        scans_completed = 0
        employer_candidates = 0
        reference_pages_inspected = 0
        reference_cache_hits = 0
        reference_fetches_deferred = 0
        reference_network_fetches_attempted = 0
        reference_evidence: list[dict[str, Any]] = []
        if strategy.dimensions.get("hypothesis_family") == "local_employer":
            fetch_reference = getattr(self.search_adapter, "fetch_reference", None)
            reference_eligible = getattr(
                self.search_adapter,
                "is_civic_reference_eligible",
                None,
            )
            reference_results = [
                item
                for item in inspected_results
                if item.classification is UrlClassification.OTHER
                and _is_civic_reference_result(item)
                and (reference_eligible is None or reference_eligible(item))
            ]
            rank_references = getattr(
                self.search_adapter,
                "rank_civic_references",
                None,
            )
            reference_results = (
                rank_references(reference_results)
                if rank_references is not None
                else sorted(reference_results, key=_civic_reference_rank)
            )
            references_acquired = 0
            for result in reference_results:
                if fetch_reference is None or references_acquired >= 2:
                    break
                cache_status_method = getattr(
                    self.search_adapter,
                    "reference_cache_status",
                    None,
                )
                cache_status = (
                    cache_status_method(result.url)
                    if cache_status_method is not None
                    else "miss"
                )
                if cache_status in {"retry_deferred", "invalid"}:
                    reference_fetches_deferred += int(cache_status == "retry_deferred")
                    reference_evidence.append(
                        {
                            "url": result.url,
                            "status": cache_status,
                            "candidate_count": 0,
                        }
                    )
                    continue
                if cache_status != "hit" and (
                    reference_network_fetches_attempted
                    >= MAX_REFERENCE_NETWORK_FETCH_ATTEMPTS
                ):
                    reference_evidence.append(
                        {
                            "url": result.url,
                            "status": "network_fetch_cap",
                            "candidate_count": 0,
                        }
                    )
                    continue
                if cache_status != "hit" and allowance.exhausted:
                    reference_evidence.append(
                        {
                            "url": result.url,
                            "status": "request_budget_exhausted",
                            "candidate_count": 0,
                        }
                    )
                    continue
                try:
                    if cache_status != "hit":
                        allowance.reserve()
                        reference_network_fetches_attempted += 1
                    fetched = await fetch_reference(result.url)
                except (RuntimeError, SearchChallengeError) as error:
                    warnings.append(str(error))
                    reference_fetches_deferred += 1
                    reference_evidence.append(
                        {
                            "url": result.url,
                            "status": "retry_deferred",
                            "candidate_count": 0,
                        }
                    )
                    continue
                references_acquired += 1
                reference_pages_inspected += 1
                document = _as_reference_document(result.url, fetched)
                reference_cache_hits += int(document.cache_status == "hit")
                candidates = _extract_employer_landscape_names(
                    document.text,
                    content_type=document.content_type,
                )
                reference_evidence.append(
                    {
                        "url": document.url,
                        "status": "inspected",
                        "candidate_count": len(candidates),
                        "cache_status": document.cache_status,
                        "content_type": document.content_type,
                    }
                )
                for candidate in candidates:
                    before = len(self.learning.list_strategies())
                    self.learning.ensure_strategy(
                        {
                            "kind": "public_search",
                            "hypothesis_family": "local_employer_deepen",
                            "anchor": candidate,
                            "location": strategy.dimensions.get("location", ""),
                            "source_domain": "web",
                            "source_path": "broad_web",
                            "employer_evidence_url": result.url,
                            "employer_evidence_authority": "civic",
                            "market_provenance": strategy.dimensions.get(
                                "market_provenance", ""
                            ),
                            "market_kind": strategy.dimensions.get("market_kind", ""),
                            "market_distance_miles": strategy.dimensions.get(
                                "market_distance_miles", ""
                            ),
                            "market_rank": strategy.dimensions.get("market_rank", ""),
                        },
                        origin="public_employer_landscape_evidence",
                    )
                    employer_candidates += int(
                        len(self.learning.list_strategies()) > before
                    )
        for result in inspected_results:
            if allowance.exhausted:
                break
            if result.classification not in {
                UrlClassification.GREENHOUSE,
                UrlClassification.LEVER,
                UrlClassification.ASHBY,
                UrlClassification.COMPANY_CAREER,
                UrlClassification.MAJOR_JOB_BOARD,
            }:
                continue
            eligible_results += 1
            try:
                self.coordinator._validate_source_policy(result.url, configuration)
                source = self.coordinator._register_source_url(
                    result.url,
                    configuration.scan_interval_minutes,
                )
                if result.classification is UrlClassification.MAJOR_JOB_BOARD:
                    source_configuration = dict(source.configuration)
                    source_configuration["direct_employer_source"] = False
                    source_configuration["source_role"] = "aggregator_listing"
                    source = self.sources.upsert(
                        source.model_copy(update={"configuration": source_configuration})
                    )
            except ValueError as error:
                warnings.append(str(error))
                continue
            source = self._attribute_source(source, strategy.id)
            registered_sources += 1
            sources_seen.add(source.id)
            if source.company_id is not None and _is_employer_source(source):
                companies_seen.add(source.company_id)
                self.learning.record_company_evidence(
                    source.company_id,
                    strategy.id,
                    location_alias=strategy.dimensions.get("location", ""),
                    provenance={
                        "search_url": result.url,
                        "search_title": result.title,
                    },
                    openings_seen=0,
                )
            scans_attempted += 1
            scan, _ = await self._scan_source(source, allowance)
            scans_completed += int(scan is not None)
            postings += len(scan.openings) if scan is not None else 0
            retained += len(scan.openings) if scan is not None else 0
            if scan is not None:
                opening_company_ids = {item.company_id for item in scan.openings}
                companies_seen.update(opening_company_ids)
                for company_id in opening_company_ids:
                    company = self.companies.get(company_id)
                    company_openings = sum(
                        item.company_id == company_id for item in scan.openings
                    )
                    self.learning.record_company_evidence(
                        company_id,
                        strategy.id,
                        location_alias=strategy.dimensions.get("location", ""),
                        provenance={
                            "source_id": source.id,
                            "search_url": result.url,
                            "search_title": result.title,
                        },
                        openings_seen=company_openings,
                    )
                    self.learning.ensure_strategy(
                        {"kind": "company_revisit", "company_id": company_id},
                        origin="aggregator_hiring_organization",
                    )
                    if company.career_url:
                        deepened_sources, _, deepened_postings = (
                            await self._deepen_company(company, strategy.id, allowance)
                        )
                        sources_seen.update(deepened_sources)
                        postings += deepened_postings
                        retained += deepened_postings
        return (
            StrategyOutcome(
                results_examined=len(inspected_results),
                companies_discovered=len(companies_seen - companies_before),
                career_sources_resolved=len(sources_seen),
                postings_inspected=postings,
                opportunities_retained=retained,
                detail={
                    "query": query,
                    "stages": {
                        "search_requests_completed": 1,
                        "search_results_returned": len(results),
                        "search_results_eligible": eligible_results,
                        "search_sources_registered": registered_sources,
                        "source_scans_attempted": scans_attempted,
                        "source_scans_completed": scans_completed,
                        "reference_pages_inspected": reference_pages_inspected,
                        "reference_cache_hits": reference_cache_hits,
                        "reference_fetches_deferred": reference_fetches_deferred,
                        "reference_network_fetches_attempted": (
                            reference_network_fetches_attempted
                        ),
                        "employer_candidates_discovered": employer_candidates,
                        "employer_reference_evidence": reference_evidence,
                    },
                },
            ),
            allowance.used - start_requests,
            warnings,
        )

    async def _execute_company_revisit(
        self,
        strategy: DiscoveryStrategySnapshot,
        allowance: _RequestAllowance | None = None,
    ) -> tuple[StrategyOutcome, int, list[str]]:
        allowance = allowance or _RequestAllowance()
        start_requests = allowance.used
        company_id = strategy.dimensions.get("company_id", "")
        try:
            company = self.companies.get(company_id)
        except KeyError as error:
            return StrategyOutcome(status="failed", failed=1), 0, [str(error)]
        sources = [item for item in self.sources.list() if item.company_id == company.id]
        if not sources:
            if company.domain.endswith(".unresolved.invalid"):
                self.learning.ensure_strategy(
                    {
                        "kind": "public_search",
                        "anchor": company.canonical_name,
                        "source_domain": "web",
                        "employer_archetype": "company careers",
                    },
                    origin="unresolved_hiring_organization",
                )
                return StrategyOutcome(), 0, []
            career_url = company.career_url or f"https://{company.domain}/careers"
            try:
                source = self.coordinator._register_source_url(
                    career_url,
                    self.coordinator.store.load().scan_interval_minutes,
                )
                sources = [self._attribute_source(source, strategy.id)]
            except ValueError as error:
                return StrategyOutcome(status="failed", failed=1), 0, [str(error)]
        postings = 0
        source_ids: set[str] = set()
        scans_attempted = 0
        scans_completed = 0
        due_ids = {item.id for item in self.sources.list_due()}
        for source in [item for item in sources if item.id in due_ids][:8]:
            if allowance.exhausted:
                break
            source = self._attribute_source(source, strategy.id)
            source_ids.add(source.id)
            scans_attempted += 1
            scan, _ = await self._scan_source(source, allowance)
            if scan is not None:
                scans_completed += 1
                postings += len(scan.openings)
        deepened, _, found = await self._deepen_company(company, strategy.id, allowance)
        source_ids.update(deepened)
        postings += found
        self.learning.record_company_evidence(
            company.id,
            strategy.id,
            provenance={"reason": "known_company_revisit"},
            openings_seen=postings,
        )
        return (
            StrategyOutcome(
                career_sources_resolved=len(source_ids),
                postings_inspected=postings,
                opportunities_retained=postings,
                detail={
                    "stages": {
                        "source_scans_attempted": scans_attempted,
                        "source_scans_completed": scans_completed,
                    }
                },
            ),
            allowance.used - start_requests,
            [],
        )

    async def _execute_source_revisit(
        self,
        strategy: DiscoveryStrategySnapshot,
        allowance: _RequestAllowance | None = None,
    ) -> tuple[StrategyOutcome, int, list[str]]:
        allowance = allowance or _RequestAllowance()
        start_requests = allowance.used
        source_id = strategy.dimensions.get("source_id", "")
        try:
            source = self.sources.get(source_id)
        except KeyError as error:
            return StrategyOutcome(status="failed", failed=1), 0, [str(error)]
        source = self._attribute_source(source, strategy.id)
        companies_before = {item.id for item in self.companies.list()}
        scan, _ = await self._scan_source(source, allowance)
        if scan is None:
            return (
                StrategyOutcome(
                    status="budget_exhausted" if allowance.exhausted else "failed",
                    failed=0 if allowance.exhausted else 1,
                    detail={
                        "stages": {
                            "source_scans_attempted": 1,
                            "source_scans_completed": 0,
                        }
                    },
                ),
                allowance.used - start_requests,
                [],
            )
        discovered_company_ids = {item.company_id for item in scan.openings}
        for company_id in discovered_company_ids:
            self.learning.record_company_evidence(
                company_id,
                strategy.id,
                provenance={"source_id": source.id, "reason": "source_revisit"},
                openings_seen=sum(item.company_id == company_id for item in scan.openings),
            )
            self.learning.ensure_strategy(
                {"kind": "company_revisit", "company_id": company_id},
                origin="source_revisit_hiring_organization",
            )
        return (
            StrategyOutcome(
                companies_discovered=len(discovered_company_ids - companies_before),
                career_sources_resolved=1,
                postings_inspected=len(scan.openings),
                opportunities_retained=len(scan.openings),
                detail={
                    "stages": {
                        "source_scans_attempted": 1,
                        "source_scans_completed": 1,
                    }
                },
            ),
            allowance.used - start_requests,
            [],
        )

    async def _scan_source(
        self,
        source: DiscoverySource,
        allowance: _RequestAllowance | None = None,
    ) -> tuple[Any | None, int]:
        allowance = allowance or _RequestAllowance()
        start_requests = allowance.used
        try:
            # Different search dimensions or company deepening can resolve to the
            # same source within one wave. Recheck durable due state here, not only
            # when selecting source-revisit strategies.
            current = self.sources.get(source.id)
            due = current.next_scan_at
            if not current.enabled or (
                due is not None
                and due.replace(tzinfo=UTC) > datetime.now(UTC)
            ):
                return None, 0
            if allowance.exhausted:
                return None, 0
            result = await self.discovery.scan_source(
                source.id,
                before_request=allowance.reserve,
            )
        except _RequestAllowanceExhausted:
            return None, allowance.used - start_requests
        except (KeyError, ValueError):
            return None, 0
        return result, allowance.used - start_requests

    async def _deepen_company(
        self,
        company: Company,
        strategy_id: str,
        allowance: _RequestAllowance | None = None,
    ) -> tuple[set[str], int, int]:
        allowance = allowance or _RequestAllowance()
        start_requests = allowance.used
        if not company.career_url:
            return set(), 0, 0
        try:
            allowance.reserve()
            urls = await self.surface_resolver.resolve(company)
        except _RequestAllowanceExhausted:
            return set(), 0, 0
        except (httpx.HTTPError, OSError, ValueError):
            return set(), allowance.used - start_requests, 0
        source_ids: set[str] = set()
        postings = 0
        for url in urls[:8]:
            if allowance.exhausted:
                break
            try:
                if "sitemap" in url.casefold() or url.casefold().endswith(".xml"):
                    source = self._register_sitemap(company, url, strategy_id)
                else:
                    source = self.coordinator._register_source_url(
                        url,
                        self.coordinator.store.load().scan_interval_minutes,
                    )
                    if source.kind in {
                        SourceKind.GREENHOUSE,
                        SourceKind.LEVER,
                        SourceKind.ASHBY,
                    }:
                        source = self.sources.upsert(
                            source.model_copy(update={"company_id": company.id})
                        )
                    source = self._attribute_source(source, strategy_id)
            except ValueError:
                continue
            source_ids.add(source.id)
            scan, _ = await self._scan_source(source, allowance)
            postings += len(scan.openings) if scan is not None else 0
        return source_ids, allowance.used - start_requests, postings

    def _register_sitemap(
        self,
        company: Company,
        url: str,
        strategy_id: str,
    ) -> DiscoverySource:
        canonical = canonicalize_url(url)
        source = DiscoverySource(
            id=stable_source_id(SourceKind.SITEMAP.value, canonical),
            company_id=company.id,
            name=f"{company.canonical_name} public sitemap",
            kind=SourceKind.SITEMAP,
            acquisition_class=AcquisitionClass.PUBLIC_STRUCTURED_FEED,
            base_url=canonical,
            configuration={"discovery_strategy_ids": [strategy_id]},
            parser_version=SitemapConnector.parser_version,
            scan_interval_minutes=self.coordinator.store.load().scan_interval_minutes,
            policy_notes="Discovered while deepening a public employer career surface.",
        )
        return self.sources.upsert(source)

    def _attribute_source(self, source: DiscoverySource, strategy_id: str) -> DiscoverySource:
        configuration = dict(source.configuration)
        strategy_ids = configuration.get("discovery_strategy_ids", [])
        if not isinstance(strategy_ids, list):
            strategy_ids = []
        configuration["discovery_strategy_ids"] = clean_list(
            [*[str(item) for item in strategy_ids], strategy_id]
        )
        return self.sources.upsert(source.model_copy(update={"configuration": configuration}))

    def _career_source_ids(self) -> set[str]:
        return {item.id for item in self.sources.list() if _is_employer_source(item)}


def _strategy_query(strategy: DiscoveryStrategySnapshot) -> str:
    anchor = strategy.dimensions.get("anchor", "").strip()
    location = strategy.dimensions.get("location", "").strip()
    source_domain = strategy.dimensions.get("source_domain", "web").strip()
    employer_archetype = strategy.dimensions.get("employer_archetype", "").strip()
    parts = [f'"{anchor}"' if anchor else "", location, employer_archetype, "jobs careers"]
    query = " ".join(item for item in parts if item).strip()
    return f"site:{source_domain} {query}" if source_domain not in {"", "web"} else query


def _clean_domain(value: str) -> str:
    domain = value.casefold().strip()
    domain = domain.removeprefix("https://").removeprefix("http://")
    return domain.split("/", 1)[0].removeprefix("www.")


def _is_employer_source(source: DiscoverySource) -> bool:
    return bool(source.configuration.get("direct_employer_source", True)) and (
        source.configuration.get("source_role") != "aggregator_listing"
    )


_REGIONAL_ORGANIZATION = re.compile(
    r"(?P<name>[A-Z][A-Za-z0-9&' .-]{2,80}?)\s+Regional\s+"
    r"(?:Council|Partnership|Commission|Authority|Planning\b)",
    re.IGNORECASE,
)
_REGIONAL_ACRONYM = re.compile(r"\b(?P<name>[A-Z]{2,6})\s+(?:Region|Area)\b")


def _extract_regional_alias_evidence(
    results: list[Any],
    *,
    anchor: str,
) -> list[dict[str, str]]:
    """Extract bounded market-language candidates from public result titles.

    Candidates only become learned search hypotheses. They do not establish a
    listing location or company office, and normal zero-yield learning can lower
    their future allocation.
    """

    found: list[dict[str, str]] = []
    seen: set[str] = set()
    anchor_key = " ".join(anchor.casefold().split())
    for result in results:
        title = " ".join(str(getattr(result, "title", "")).split())
        matches = [
            match.group("name")
            for pattern in (_REGIONAL_ORGANIZATION, _REGIONAL_ACRONYM)
            for match in pattern.finditer(title)
        ]
        for raw in matches:
            alias = re.split(r"[|:–—]|\s+-\s+", raw)[-1].strip(" ,-.")
            alias = re.sub(
                r"^(?:about|welcome to|official site of)\s+",
                "",
                alias,
                flags=re.IGNORECASE,
            )
            key = " ".join(alias.casefold().split())
            if not key or key == anchor_key or key in seen or len(alias) < 3:
                continue
            seen.add(key)
            found.append(
                {
                    "alias": alias,
                    "title": title[:300],
                    "url": str(getattr(result, "url", ""))[:1000],
                }
            )
            if len(found) >= 6:
                return found
    return found


def _extract_employer_landscape_names(
    content: str,
    *,
    content_type: str = "text/html",
) -> list[str]:
    """Extract bounded employer-name hypotheses under an employer-list heading."""

    structured = _extract_structured_employer_names(content, content_type)
    parser = _EmployerLandscapeParser()
    parser.feed(content)
    parser.close()
    marker: tuple[int, int] | None = None
    for index, (_tag, level, text) in enumerate(parser.items):
        if level is None:
            continue
        normalized = " ".join(text.casefold().split())
        if re.search(r"\b(?:major|top|largest)\s+employers?\b", normalized):
            marker = (index, level)
            break
    if marker is None:
        return structured
    start, marker_level = marker
    candidates: list[str] = list(structured)
    seen: set[str] = {item.casefold() for item in candidates}
    for tag, level, text in parser.items[start + 1 :]:
        if level is not None and level <= marker_level:
            break
        candidate = " ".join(text.split()).strip(" |:-")
        key = candidate.casefold()
        if (
            not 2 <= len(candidate) <= 100
            or not 1 <= len(candidate.split()) <= 10
            or key in seen
            or key.startswith(("contact ", "learn ", "about "))
            or (tag in {"li", "td"} and len(candidate.split()) > 8)
        ):
            continue
        seen.add(key)
        candidates.append(candidate)
        if len(candidates) >= 12:
            break
    return candidates


def _as_reference_document(url: str, fetched: Any) -> ReferenceDocument:
    if isinstance(fetched, ReferenceDocument):
        return fetched
    return ReferenceDocument(
        url=url,
        text=str(fetched),
        content_type="text/html",
        cache_status="unavailable",
    )


def _extract_structured_employer_names(content: str, content_type: str) -> list[str]:
    """Read employer names from JSON APIs and schema.org JSON-LD lists."""

    documents: list[Any] = []
    if "json" in content_type.casefold() or content.lstrip().startswith(("{", "[")):
        try:
            documents.append(json.loads(content))
        except json.JSONDecodeError:
            return []
    else:
        scripts = re.findall(
            r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
            content,
            flags=re.IGNORECASE | re.DOTALL,
        )
        for script in scripts:
            try:
                documents.append(json.loads(script))
            except json.JSONDecodeError:
                continue

    found: list[str] = []
    seen: set[str] = set()

    def add(value: Any) -> None:
        candidate = " ".join(str(value or "").split()).strip(" |:-")
        key = candidate.casefold()
        if 2 <= len(candidate) <= 100 and 1 <= len(candidate.split()) <= 10 and key not in seen:
            seen.add(key)
            found.append(candidate)

    def walk(
        value: Any,
        *,
        directory_context: bool = False,
        organization_context: bool = False,
    ) -> None:
        if len(found) >= 12:
            return
        if isinstance(value, list):
            for item in value:
                walk(
                    item,
                    directory_context=directory_context,
                    organization_context=organization_context,
                )
            return
        if not isinstance(value, dict):
            if organization_context:
                add(value)
            return
        if organization_context:
            add(value.get("name"))
        kind = value.get("@type")
        kinds = {str(item).casefold() for item in (kind if isinstance(kind, list) else [kind])}
        if "itemlist" in kinds:
            walk(value.get("itemListElement", []), directory_context=True)
            return
        is_organization = bool(
            kinds
            & {
                "corporation",
                "localbusiness",
                "organization",
            }
        )
        if is_organization and directory_context:
            add(value.get("name"))
        for key, item in value.items():
            normalized = re.sub(r"[^a-z]", "", str(key).casefold())
            employer_field = normalized in {
                "businessname",
                "company",
                "companyname",
                "employer",
                "employername",
                "organization",
                "organizationname",
            }
            if employer_field and isinstance(item, str):
                add(item)
            else:
                walk(
                    item,
                    directory_context=directory_context,
                    organization_context=employer_field,
                )

    for document in documents:
        walk(document)
    return found[:12]


def _is_civic_reference_result(result: Any) -> bool:
    """Prefer accountable public/regional sources for employer hypotheses."""

    domain = (urlsplit(str(getattr(result, "url", ""))).hostname or "").casefold()
    compact = re.sub(r"[^a-z]", "", domain)
    return domain.endswith((".gov", ".org")) or any(
        marker in compact
        for marker in ("economicdevelopment", "chamber", "partnership", "council")
    )


def _civic_reference_rank(result: Any) -> tuple[int, str]:
    domain = (urlsplit(str(getattr(result, "url", ""))).hostname or "").casefold()
    compact = re.sub(r"[^a-z]", "", domain)
    if domain.endswith(".gov"):
        priority = 0
    elif "economicdevelopment" in compact or "chamber" in compact:
        priority = 1
    else:
        priority = 2
    return priority, domain


def _reflection_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["strategies"],
        "properties": {
            "strategies": {
                "type": "array",
                "maxItems": 6,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["anchor", "rationale"],
                    "properties": {
                        "anchor": {"type": "string", "minLength": 1, "maxLength": 120},
                        "location": {"type": "string", "maxLength": 120},
                        "source_domain": {"type": "string", "maxLength": 200},
                        "employer_archetype": {"type": "string", "maxLength": 120},
                        "rationale": {"type": "string", "minLength": 1, "maxLength": 500},
                    },
                },
            }
        },
    }
