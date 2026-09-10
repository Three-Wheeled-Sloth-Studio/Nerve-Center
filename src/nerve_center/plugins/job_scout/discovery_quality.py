"""Issue #43 source-aware discovery quality layered on the accepted Job Scout loop."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from nerve_center.plugins.job_scout.discovery_learning import (
    CompanyDiscoveryEvidenceModel,
    DiscoverySessionModel,
    DiscoveryStrategyModel,
    DiscoveryStrategySnapshot,
    JobScoutDiscoveryRepository,
    StrategyAttemptModel,
    StrategyOutcome,
)
from nerve_center.plugins.job_scout.discovery_loop import JobScoutDiscoveryLoop
from nerve_center.plugins.job_scout.query_portfolio import (
    STRUCTURED_SOURCE_KINDS,
    build_coverage_gap_profile,
    build_query_portfolio,
    compile_strategy_query,
)
from nerve_center.plugins.job_scout.settings import clean_list


class DiscoveryQualityRepository(JobScoutDiscoveryRepository):
    """Persistence helpers for overlap priority and human-readable audit data."""

    def record_attempt(
        self,
        run_id: str,
        cycle: int,
        strategy_id: str,
        phase: str,
        outcome: StrategyOutcome,
        *,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> DiscoveryStrategySnapshot:
        before = self.get_strategy(strategy_id).learned_weight
        result = super().record_attempt(
            run_id,
            cycle,
            strategy_id,
            phase,
            outcome,
            started_at=started_at,
            finished_at=finished_at,
        )
        with self.database.session() as session:
            attempt = session.scalar(
                select(StrategyAttemptModel)
                .where(
                    StrategyAttemptModel.run_id == run_id,
                    StrategyAttemptModel.cycle == cycle,
                    StrategyAttemptModel.strategy_id == strategy_id,
                    StrategyAttemptModel.phase == phase,
                )
                .order_by(StrategyAttemptModel.finished_at.desc())
            )
            if attempt is not None:
                detail = dict(attempt.detail or {})
                detail["weight_before"] = round(before, 3)
                detail["weight_after"] = round(result.learned_weight, 3)
                attempt.detail = detail
        return result

    def record_company_evidence(
        self,
        company_id: str,
        strategy_id: str,
        *,
        location_alias: str = "",
        provenance: dict[str, Any] | None = None,
        openings_seen: int = 0,
        now: datetime | None = None,
    ) -> None:
        super().record_company_evidence(
            company_id,
            strategy_id,
            location_alias=location_alias,
            provenance=provenance,
            openings_seen=openings_seen,
            now=now,
        )
        self._promote_converged_company(company_id, now=now)

    def promote_initial_structured_refresh(
        self,
        strategy_id: str,
        *,
        floor: float = 1.35,
        now: datetime | None = None,
    ) -> None:
        """Favor a newly known structured source once, then let observed yield learn normally."""

        current = now or datetime.now(UTC)
        with self.database.session() as session:
            model = session.get(DiscoveryStrategyModel, strategy_id)
            if model is None or model.attempts > 0 or model.learned_weight >= floor:
                return
            model.learned_weight = floor
            model.updated_at = current

    def set_session_audit(
        self,
        run_id: str,
        *,
        coverage_gaps: dict[str, list[str]],
        now: datetime | None = None,
    ) -> None:
        current = now or datetime.now(UTC)
        with self.database.session() as session:
            model = session.get(DiscoverySessionModel, run_id)
            if model is None:
                return
            coverage = dict(model.coverage or {})
            coverage["coverage_gaps"] = coverage_gaps
            model.coverage = coverage
            model.updated_at = current

    def discovery_audit(self) -> dict[str, Any]:
        with self.database.session() as session:
            strategies = session.scalars(
                select(DiscoveryStrategyModel).order_by(
                    DiscoveryStrategyModel.learned_weight.desc(),
                    DiscoveryStrategyModel.updated_at.desc(),
                )
            ).all()
            attempts = session.scalars(
                select(StrategyAttemptModel).order_by(StrategyAttemptModel.finished_at.desc())
            ).all()
            latest_by_strategy: dict[str, StrategyAttemptModel] = {}
            for attempt in attempts:
                latest_by_strategy.setdefault(attempt.strategy_id, attempt)
            evidence = session.scalars(select(CompanyDiscoveryEvidenceModel)).all()
            strategy_companies: dict[str, set[str]] = {}
            company_strategies: dict[str, set[str]] = {}
            for item in evidence:
                strategy_companies.setdefault(item.strategy_id, set()).add(item.company_id)
                company_strategies.setdefault(item.company_id, set()).add(item.strategy_id)
            latest_session = session.scalar(
                select(DiscoverySessionModel).order_by(DiscoverySessionModel.updated_at.desc())
            )

            rows: list[dict[str, Any]] = []
            for strategy in strategies:
                latest = latest_by_strategy.get(strategy.id)
                detail = dict(latest.detail or {}) if latest is not None else {}
                overlap_companies = sorted(
                    company_id
                    for company_id in strategy_companies.get(strategy.id, set())
                    if len(company_strategies.get(company_id, set())) > 1
                )
                rows.append(
                    {
                        "id": strategy.id,
                        "hypothesis_family": strategy.dimensions.get(
                            "hypothesis_family", "legacy"
                        ),
                        "anchor": strategy.dimensions.get("anchor", ""),
                        "location": strategy.dimensions.get("location", ""),
                        "source_domain": strategy.dimensions.get("source_domain", ""),
                        "source_path": detail.get(
                            "source_path", strategy.dimensions.get("source_path", "")
                        ),
                        "compiled_query": detail.get("query", ""),
                        "learned_weight": round(float(strategy.learned_weight), 3),
                        "weight_before": detail.get("weight_before"),
                        "weight_after": detail.get("weight_after"),
                        "attempts": strategy.attempts,
                        "total_yield": int(
                            detail.get(
                                "total_opportunities_retained",
                                strategy.opportunities_retained,
                            )
                        ),
                        "conditioned_yield": int(
                            detail.get(
                                "location_conditioned_retained",
                                strategy.opportunities_retained,
                            )
                        ),
                        "warnings": list(detail.get("warnings", [])),
                        "overlap_company_count": len(overlap_companies),
                        "overlap_company_ids": overlap_companies[:8],
                        "last_attempt_at": strategy.last_attempt_at,
                    }
                )
            coverage = (
                dict(latest_session.coverage or {}) if latest_session is not None else {}
            )
            return {
                "run_id": latest_session.run_id if latest_session is not None else None,
                "coverage_gaps": coverage.get("coverage_gaps", {}),
                "strategies": rows[:120],
            }

    def _promote_converged_company(
        self,
        company_id: str,
        *,
        now: datetime | None = None,
    ) -> None:
        current = now or datetime.now(UTC)
        with self.database.session() as session:
            evidence = session.scalars(
                select(CompanyDiscoveryEvidenceModel).where(
                    CompanyDiscoveryEvidenceModel.company_id == company_id
                )
            ).all()
            distinct_strategies = {item.strategy_id for item in evidence}
            if len(distinct_strategies) < 2:
                return
            floor = min(1.75, 1.0 + 0.15 * (len(distinct_strategies) - 1))
            strategies = session.scalars(select(DiscoveryStrategyModel)).all()
            for strategy in strategies:
                if (
                    strategy.dimensions.get("kind") == "company_revisit"
                    and strategy.dimensions.get("company_id") == company_id
                    and strategy.learned_weight < floor
                ):
                    strategy.learned_weight = floor
                    strategy.updated_at = current


class SourceAwareJobScoutDiscoveryLoop(JobScoutDiscoveryLoop):
    """Compile source-appropriate experiments and reflect against explicit coverage gaps."""

    async def prepare(self, run_id: str) -> dict[str, Any]:
        result = await super().prepare(run_id)
        gaps = self._coverage_gaps()
        self._record_gaps(run_id, gaps)
        return {**result, "coverage_gaps": gaps}

    def _seed_search_strategies(
        self,
        anchors: list[str],
        locations: list[str],
        boards: list[str],
    ) -> None:
        configuration = self.coordinator.store.load()
        keywords = self.coordinator._discover_keywords(configuration).keywords or anchors
        source_domains = [
            *boards,
            "job-boards.greenhouse.io",
            "jobs.lever.co",
            "jobs.ashbyhq.com",
        ]
        portfolio = build_query_portfolio(
            target_titles=configuration.target_titles,
            keywords=keywords,
            locations=locations,
            source_domains=source_domains,
            limit=96,
        )
        for dimensions in portfolio:
            self.learning.ensure_strategy(dimensions, origin="source_aware_portfolio")

    def _seed_due_source_strategies(self) -> None:
        for source in self.sources.list_due():
            if not source.configuration.get("direct_employer_source", True):
                continue
            strategy = self.learning.ensure_strategy(
                {"kind": "source_revisit", "source_id": source.id},
                origin="known_source",
            )
            if (
                source.kind in STRUCTURED_SOURCE_KINDS
                and isinstance(self.learning, DiscoveryQualityRepository)
            ):
                self.learning.promote_initial_structured_refresh(strategy.id)

    async def _execute_public_search(
        self,
        strategy: Any,
    ) -> tuple[StrategyOutcome, int, list[str]]:
        configuration = self.coordinator.store.load()
        evidence_terms = [
            *configuration.target_titles,
            *configuration.manual_keywords,
            *self.coordinator._discover_keywords(configuration).keywords,
        ]
        compiled = compile_strategy_query(
            strategy.dimensions,
            evidence_terms=evidence_terms,
        )
        if not compiled.valid:
            warnings = list(compiled.warnings) or ["query_rejected"]
            return (
                StrategyOutcome(
                    status="rejected",
                    failed=1,
                    detail={
                        "hypothesis_family": strategy.dimensions.get(
                            "hypothesis_family", "legacy"
                        ),
                        "source_path": compiled.source_path,
                        "warnings": warnings,
                        "query_rejected": True,
                    },
                ),
                0,
                warnings,
            )

        original_adapter = self.search_adapter
        self.search_adapter = _CompiledQueryAdapter(original_adapter, compiled.query)
        try:
            outcome, requests, warnings = await super()._execute_public_search(strategy)
        finally:
            self.search_adapter = original_adapter
        detail = {
            **outcome.detail,
            "query": compiled.query,
            "hypothesis_family": strategy.dimensions.get(
                "hypothesis_family", "legacy"
            ),
            "source_path": compiled.source_path,
            "warnings": clean_list([*compiled.warnings, *warnings]),
        }
        return (
            replace(outcome, detail=detail),
            requests,
            clean_list([*compiled.warnings, *warnings]),
        )

    def deterministic_reflection(self, run_id: str, cycle: int) -> dict[str, Any]:
        gaps = self._coverage_gaps()
        self._record_gaps(run_id, gaps)
        existing_ids = {item.id for item in self.learning.list_strategies()}
        configuration = self.coordinator.store.load()
        first_title = (configuration.target_titles or ["product management"])[0]
        proposals: list[tuple[str, dict[str, str]]] = []
        for role in gaps.get("role", [])[:2]:
            proposals.append(
                (
                    f"Cover missing role evidence: {role}",
                    self._gap_dimensions("direct_role", role),
                )
            )
        for term in gaps.get("domain_capability", [])[:2]:
            proposals.append(
                (
                    f"Cover missing capability evidence: {term}",
                    self._gap_dimensions("domain_capability", term),
                )
            )
        for location in gaps.get("geography", [])[:2]:
            proposals.append(
                (
                    f"Cover missing market evidence: {location}",
                    {
                        **self._gap_dimensions("direct_role", first_title),
                        "location": location,
                    },
                )
            )
        created = 0
        for hypothesis, dimensions in proposals[:6]:
            strategy = self.learning.ensure_strategy(dimensions, origin="gap_reflection")
            if strategy.id in existing_ids:
                continue
            existing_ids.add(strategy.id)
            created += 1
            self.learning.record_reflection_hypothesis(
                run_id,
                cycle,
                origin="deterministic_gap",
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
                "llm_recommended": False,
                "coverage_gaps": gaps,
            }
        inherited = super().deterministic_reflection(run_id, cycle)
        return {**inherited, "coverage_gaps": gaps}

    def reflection_work_request(self, run_id: str, cycle: int) -> dict[str, Any]:
        gaps = self._coverage_gaps()
        self._record_gaps(run_id, gaps)
        request = super().reflection_work_request(run_id, cycle)
        payload = dict(request["payload"])
        payload["user_prompt"] = (
            "Use the explicit uncovered-space profile below as the primary assignment. Propose "
            "up to six materially different public discovery strategies that target real gaps, "
            "not superficial query rewordings. Preserve broad exploration. "
            f"Coverage gaps: {gaps}. {payload['user_prompt']}"
        )
        request["payload"] = payload
        request["output_contract"] = _quality_reflection_schema()
        request["requirements"] = {
            "contract_version": "job-scout-discovery-reflection-v2"
        }
        return request

    def apply_reflection_result(self, request_id: str, value: dict[str, Any]) -> int:
        request = self.learning.reflection_request(request_id)
        if request is None or request["status"] == "applied":
            return 0
        created = 0
        known_ids = {item.id for item in self.learning.list_strategies()}
        strategies = value.get("strategies", [])
        if not isinstance(strategies, list):
            raise ValueError("reflection result strategies must be a list")
        evidence_terms = self._evidence_terms()
        for item in strategies[:6]:
            if not isinstance(item, dict):
                continue
            family = str(item.get("hypothesis_family") or "gap_reflection").strip()
            dimensions = {
                "kind": "public_search",
                "hypothesis_family": family,
                "anchor": str(item.get("anchor") or "").strip(),
                "location": str(item.get("location") or "").strip(),
                "source_domain": str(item.get("source_domain") or "web").strip(),
                "employer_archetype": str(
                    item.get("employer_archetype") or ""
                ).strip(),
            }
            compiled = compile_strategy_query(dimensions, evidence_terms=evidence_terms)
            if not compiled.valid:
                continue
            strategy = self.learning.ensure_strategy(
                dimensions,
                origin="llm_gap_reflection",
            )
            if strategy.id in known_ids:
                continue
            known_ids.add(strategy.id)
            created += 1
            self.learning.record_reflection_hypothesis(
                str(request["run_id"]),
                int(request["cycle"]),
                origin="llm_gap",
                hypothesis=str(
                    item.get("rationale") or "LLM-proposed uncovered search path"
                ),
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

    def _coverage_gaps(self) -> dict[str, list[str]]:
        configuration = self.coordinator.store.load()
        return build_coverage_gap_profile(
            target_titles=configuration.target_titles,
            keywords=self.coordinator._discover_keywords(configuration).keywords,
            locations=configuration.locations,
            remote_preference=configuration.remote_preference,
            strategies=self.learning.list_strategies(),
            openings=self.jobs.list(active_only=False),
            sources=self.sources.list(),
        )

    def _record_gaps(self, run_id: str, gaps: dict[str, list[str]]) -> None:
        if isinstance(self.learning, DiscoveryQualityRepository):
            self.learning.set_session_audit(run_id, coverage_gaps=gaps)

    def _gap_dimensions(self, family: str, anchor: str) -> dict[str, str]:
        return {
            "kind": "public_search",
            "hypothesis_family": family,
            "anchor": anchor,
            "source_domain": "web",
            "source_path": "broad_web",
        }

    def _evidence_terms(self) -> list[str]:
        configuration = self.coordinator.store.load()
        return clean_list(
            [
                *configuration.target_titles,
                *configuration.manual_keywords,
                *self.coordinator._discover_keywords(configuration).keywords,
            ]
        )


class _CompiledQueryAdapter:
    """Run one compiled query through accepted adapter without duplicating deepening logic."""

    def __init__(self, delegate: Any, query: str) -> None:
        self.delegate = delegate
        self.query = query

    async def search(self, _legacy_query: str) -> Any:
        return await self.delegate.search(self.query)


def _quality_reflection_schema() -> dict[str, Any]:
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
                        "hypothesis_family": {
                            "type": "string",
                            "enum": [
                                "direct_role",
                                "adjacent_role",
                                "seniority_variant",
                                "domain_capability",
                                "employer_archetype",
                                "gap_reflection",
                            ],
                        },
                        "anchor": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": 120,
                        },
                        "location": {"type": "string", "maxLength": 120},
                        "source_domain": {"type": "string", "maxLength": 200},
                        "employer_archetype": {
                            "type": "string",
                            "maxLength": 120,
                        },
                        "rationale": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": 500,
                        },
                    },
                },
            }
        },
    }
