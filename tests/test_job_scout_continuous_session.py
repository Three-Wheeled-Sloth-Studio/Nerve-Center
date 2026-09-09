import asyncio
from copy import deepcopy
from dataclasses import asdict
from datetime import UTC, datetime, timedelta

from fastapi import FastAPI
from test_job_scout_discovery_loop import (
    SearchResult,
    UrlClassification,
    _build_loop,
    _FixtureSearch,
)

from nerve_center.config import Settings
from nerve_center.plugins.job_scout import worker
from nerve_center.plugins.job_scout.runtime import JobScoutOperationBridge
from nerve_center.providers.base import ProviderCallMetadata, StructuredGenerationResult
from nerve_center.scoring.api import register_scoring_routes


class FitProvider:
    name = "fixture"

    async def generate_structured(self, **kwargs):
        assert kwargs["model"] == "auto"
        value = kwargs["response_type"](
            qualifications=[], seniority_score=50, domain_score=50, leadership_score=50,
            methods_score=50, outcomes_score=50, confidence=0.5,
        )
        return StructuredGenerationResult(
            value=value,
            metadata=ProviderCallMetadata(
                id="fit", provider="fixture", model="fixture",
                contract_version=kwargs["contract_version"], response_schema="fixture",
                duration_ms=1, status="succeeded",
            ),
        )


class Client:
    def __init__(self, bridge, *, drain_after=None):
        self.bridge = bridge
        self.cycles = 0
        self.drain_after = drain_after
        self.checkpoints = []
        self.pending = []
        self.usage = {"requests": 0, "llm_calls": 0}
        self.reflections = 0
        self.final = None

    async def invoke(self, run_id, operation, payload=None):
        result = await self.bridge.invoke(operation, payload or {})
        if operation == "discovery_cycle":
            self.cycles += 1
            result["needs_reflection"] = True
        return result

    async def control(self, run_id):
        return {
            "budget_usage": dict(self.usage), "cancel_requested": False,
            "shutdown_requested": False, "accept_new_llm_work": True,
            "admission_phase": "draining" if self.drain_after == self.cycles else "open",
        }

    async def checkpoint(self, run_id, checkpoint):
        self.checkpoints.append(deepcopy(checkpoint))

    async def consume(self, run_id, resource, count=1):
        self.usage[resource] += count

    async def submit_work(self, run_id, request):
        self.reflections += 1
        request_id = f"reflection-{self.reflections}"
        self.pending = [{
            "id": request_id, "request_id": request_id,
            "payload": {"value": {"strategies": []}},
        }]
        return {"id": request_id}

    async def results(self):
        return self.pending

    async def acknowledge_result(self, *args, **kwargs):
        self.pending = []

    async def complete(self, run_id, status, summary, metrics):
        self.final = (status, metrics)

    async def heartbeat(self, *args, **kwargs):
        pass


def setup_bridge(tmp_path, monkeypatch, *, empty=False):
    search = _FixtureSearch(results=[] if empty else [SearchResult(
        title="Example careers", url="https://example.com/careers",
        classification=UrlClassification.COMPANY_CAREER, domain="example.com",
    )])
    loop, learning, companies, sources, jobs, coordinator = _build_loop(
        tmp_path, search=search,
    )
    scoring = register_scoring_routes(
        FastAPI(), learning.database, Settings(data_dir=tmp_path / "runtime"), FitProvider(),
    )
    monkeypatch.setattr(loop, "deterministic_reflection", lambda *args: {
        "new_strategies": 0, "llm_recommended": True,
    })
    if empty:
        original = loop.cycle

        async def empty_cycle(run_id, cycle):
            result = await original(run_id, cycle)
            return type(result)(**{
                **asdict(result), "strategies_attempted": 0, "strategies_exhausted": True,
            })

        monkeypatch.setattr(loop, "cycle", empty_cycle)
    bridge = JobScoutOperationBridge(loop.discovery, sources, coordinator, learning, loop, scoring)
    return bridge, scoring, jobs


def assignment():
    return {
        "run_id": "run", "deadline": (datetime.now(UTC) + timedelta(hours=8)).isoformat(),
        "resource_policy": {"max_requests": 500, "max_llm_calls": 100},
    }


def test_two_waves_score_before_drain_despite_empty_reflection(tmp_path, monkeypatch):
    bridge, scoring, jobs = setup_bridge(tmp_path, monkeypatch)
    client = Client(bridge, drain_after=2)
    asyncio.run(worker._execute_discovery_loop(client, assignment()))

    assert jobs.list(), "wave one must persist a retained opportunity"
    assert any(
        score.calculation["fit_model"] == "fixture"
        for job in jobs.list() for score in scoring.scores.list(job.id)
    )
    assert client.reflections == 1
    assert client.cycles == 2
    assert any(item.dimensions.get("kind") == "company_revisit" and item.attempts
               for item in bridge.learning.list_strategies())
    checkpoints = client.checkpoints
    scored = next(i for i, item in enumerate(checkpoints) if item["full_scores_completed"])
    second_wave = next(i for i, item in enumerate(checkpoints) if item["wave"] == 2)
    assert scored < second_wave
    assert checkpoints[second_wave]["reflection_outcome"] == "no_new_strategies"
    assert client.final[0] == "partial"
    assert client.final[1]["terminal_reason"] == "admission_draining"


def test_no_work_has_paced_refresh_and_no_repeated_unchanged_reflection(tmp_path, monkeypatch):
    bridge, _, _ = setup_bridge(tmp_path, monkeypatch, empty=True)
    client = Client(bridge)
    sleeps = []
    original_sleep = asyncio.sleep

    async def fake_sleep(seconds):
        if seconds == 5:
            sleeps.append(seconds)
        await original_sleep(0)

    monkeypatch.setattr(worker.asyncio, "sleep", fake_sleep)
    asyncio.run(worker._execute_discovery_loop(client, assignment()))
    assert sum(sleeps) == 210
    assert client.reflections == 1
    assert client.cycles == 4
    assert client.final[1]["terminal_reason"] == "no_work_after_three_refresh_backoffs"
    assert [item["backoff_seconds"] for item in client.checkpoints
            if item["phase"] == "backoff"] == [30, 60, 120]
