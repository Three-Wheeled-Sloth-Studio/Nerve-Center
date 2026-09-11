"""Location-aware Job Scout discovery learning without narrowing retained inventory."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from sqlalchemy import select

from nerve_center.plugins.job_scout.discovery_learning import (
    DiscoveryStrategyModel,
    JobScoutDiscoveryRepository,
    StrategyAttemptModel,
)
from nerve_center.plugins.job_scout.discovery_loop import (
    DiscoveryCycleSummary,
    _clean_domain,
    _is_employer_source,
    _RequestAllowance,
)
from nerve_center.plugins.job_scout.discovery_quality import SourceAwareJobScoutDiscoveryLoop
from nerve_center.plugins.job_scout.settings import clean_list
from nerve_center.scoring.location import opening_matches_market


class LocationAwareJobScoutDiscoveryLoop(SourceAwareJobScoutDiscoveryLoop):
    """Preserve total discovery while learning location strategies from local yield."""

    async def prepare(self, run_id: str) -> dict[str, object]:
        normalized = _normalize_legacy_location_strategy_yield(self.learning)
        result = await super().prepare(run_id)
        return {**result, "legacy_location_strategies_normalized": normalized}

    async def cycle(
        self,
        run_id: str,
        cycle: int,
        request_limit: int | None = None,
    ) -> DiscoveryCycleSummary:
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
            jobs_before = {
                item.id: item for item in self.jobs.list(active_only=False)
            }
            outcome, used_requests, strategy_warnings = await self._execute_strategy(
                strategy,
                allowance,
            )
            jobs_after = {
                item.id: item for item in self.jobs.list(active_only=False)
            }
            new_jobs = [
                item for job_id, item in jobs_after.items() if job_id not in jobs_before
            ]
            total_retained = len(new_jobs)
            location_alias = strategy.dimensions.get("location", "").strip()
            conditioned_retained = (
                sum(opening_matches_market(item, location_alias) for item in new_jobs)
                if location_alias
                else total_retained
            )
            detail = {
                **outcome.detail,
                "total_opportunities_retained": total_retained,
                "location_conditioned_retained": conditioned_retained,
                "yield_scope": "location_conditioned" if location_alias else "total",
            }
            if location_alias:
                detail["location_alias"] = location_alias

            # Strategy learning sees only opening yield that actually matches the
            # strategy's location. Total retained inventory remains durable and is
            # still counted in session coverage below. Company/source discovery is
            # intentionally still useful general market evidence.
            learning_outcome = replace(
                outcome,
                career_sources_resolved=len(
                    self._career_source_ids() - source_ids_before
                ),
                postings_inspected=(
                    conditioned_retained if location_alias else outcome.postings_inspected
                ),
                opportunities_retained=conditioned_retained,
                detail=detail,
            )
            self.learning.record_attempt(
                run_id,
                cycle,
                strategy.id,
                "deepen",
                learning_outcome,
            )
            request_count += used_requests
            useful_yield += learning_outcome.useful_yield
            openings_found += total_retained
            warnings.extend(strategy_warnings)
            increments["strategies_attempted"] += 1
            increments["results_examined"] += outcome.results_examined
            increments["companies_discovered"] += outcome.companies_discovered
            increments["career_sources_resolved"] += learning_outcome.career_sources_resolved
            increments["postings_inspected"] += outcome.postings_inspected
            increments["opportunities_retained"] += total_retained
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
        gaps = self._coverage_gaps()
        self._record_gaps(run_id, gaps)
        coverage = dict(session.coverage)
        coverage["coverage_gaps"] = gaps
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
            coverage=coverage,
            yield_metrics=increments,
        )


def _normalize_legacy_location_strategy_yield(
    learning: JobScoutDiscoveryRepository,
) -> int:
    """Remove pre-Issue-40 distant-opening credit from location strategies once."""

    normalized = 0
    now = datetime.now(UTC)
    with learning.database.session() as session:
        strategies = session.scalars(select(DiscoveryStrategyModel)).all()
        for strategy in strategies:
            if not strategy.dimensions.get("location"):
                continue
            attempts = session.scalars(
                select(StrategyAttemptModel).where(
                    StrategyAttemptModel.strategy_id == strategy.id
                )
            ).all()
            instrumented = [
                item
                for item in attempts
                if isinstance(item.detail, dict)
                and "location_conditioned_retained" in item.detail
            ]
            if instrumented:
                conditioned = sum(
                    max(int(item.detail.get("location_conditioned_retained", 0)), 0)
                    for item in instrumented
                )
                if strategy.opportunities_retained != conditioned:
                    strategy.opportunities_retained = conditioned
                    strategy.updated_at = now
                    normalized += 1
                continue
            if strategy.opportunities_retained <= 0:
                continue
            strategy.opportunities_retained = 0
            strategy.learned_weight = _clamp(
                1.0 + (strategy.positive_feedback - strategy.negative_feedback) * 0.08,
                0.2,
                4.0,
            )
            strategy.updated_at = now
            normalized += 1
    return normalized


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))
