import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from nerve_center.api.app import create_app
from nerve_center.config import Settings
from nerve_center.domain.run_window import DurationRunWindow
from nerve_center.domain.work_queue import WorkClass, WorkRequestSpec
from nerve_center.model_lab.service import (
    ModelLabBusyError,
    ModelLabDisabledError,
    ModelLabService,
)
from nerve_center.persistence.database import Database
from nerve_center.persistence.model_lab import ModelLabRepository
from nerve_center.persistence.providers import ModelEvidenceRepository
from nerve_center.persistence.runs import RunRepository
from nerve_center.persistence.work_queue import WorkQueueRepository
from nerve_center.providers.base import (
    JsonGenerationResult,
    ModelBlindRequest,
    ProviderCallMetadata,
    ProviderModel,
)
from nerve_center.providers.manager import ProviderManager
from nerve_center.scheduler.work_queue import WorkQueueService


class FakeJsonProvider:
    name = "ollama"

    def __init__(self, value: dict[str, Any] | None = None) -> None:
        self.value = value or {"score": 92}
        self.selected_models: list[str] = []

    async def list_models(self) -> list[ProviderModel]:
        return [
            ProviderModel(
                id="local-model",
                label="Local Model",
                family="test",
                parameter_size="4B",
            )
        ]

    async def generate_json(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        output_schema: dict[str, Any],
        contract_version: str,
    ) -> JsonGenerationResult:
        del system_prompt, user_prompt, output_schema
        self.selected_models.append(model)
        return JsonGenerationResult(
            value=self.value,
            metadata=ProviderCallMetadata(
                id=f"benchmark-call-{len(self.selected_models)}",
                provider=self.name,
                model=model,
                contract_version=contract_version,
                response_schema="json_schema",
                started_at=datetime.now(UTC),
                duration_ms=31,
                status="succeeded",
            ),
        )


def _context(tmp_path: Path) -> tuple[
    Database,
    WorkQueueService,
    ModelEvidenceRepository,
    ModelLabRepository,
    ModelLabService,
    ProviderManager,
    str,
]:
    database = Database(Settings(data_dir=tmp_path))
    database.initialize()
    evidence = ModelEvidenceRepository(database)
    queue = WorkQueueService(WorkQueueRepository(database), model_evidence=evidence)
    repository = ModelLabRepository(database)
    manager = ProviderManager((FakeJsonProvider(),), evidence=evidence)
    service = ModelLabService(repository, evidence, manager, queue)
    run = RunRepository(database).create(
        "job_scout.discovery", DurationRunWindow(timedelta(minutes=5))
    )
    return database, queue, evidence, repository, service, manager, run.id


def _completed_request(
    queue: WorkQueueService,
    run_id: str,
    *,
    module_id: str = "job_scout",
    idempotency_key: str = "model-lab-example",
    requirements: dict[str, Any] | None = None,
    user_prompt: str = "Evaluate this job.",
) -> str:
    request = queue.submit(
        WorkRequestSpec(
            module_id=module_id,
            run_id=run_id,
            task_id="job_scout.evaluate_fit",
            work_class=WorkClass.LLM,
            payload={
                "system_prompt": "Use token=super-secret only as a test fixture.",
                "user_prompt": user_prompt,
            },
            output_contract={
                "type": "object",
                "properties": {"score": {"type": "integer"}},
                "required": ["score"],
            },
            requirements={"contract_version": "fit-v1", **(requirements or {})},
            idempotency_key=idempotency_key,
            module_priority=100,
            task_priority=70,
        )
    )
    attempt = queue.claim_next("fixture", (WorkClass.LLM,))
    assert attempt is not None
    queue.complete(
        attempt.id,
        {
            "value": {"score": 91, "secret": "do-not-retain"},
            "manager": {
                "provider_call_id": "production-call-1",
                "provider": "ollama",
                "model": "local-model",
                "schema_valid": True,
            },
        },
    )
    return request.id


def test_harvest_is_deduplicated_local_and_secret_safe(tmp_path: Path) -> None:
    _, queue, _, repository, service, _, run_id = _context(tmp_path)
    _completed_request(
        queue,
        run_id,
        requirements={"api_key": "should-not-survive"},
    )

    assert service.harvest() == 1
    assert service.harvest() == 0

    items = repository.list_corpus()
    assert len(items) == 1
    item = items[0]
    assert item.module_id == "job_scout"
    assert item.task_id == "job_scout.evaluate_fit"
    assert item.contract_version == "fit-v1"
    assert "super-secret" not in item.system_prompt
    assert "[REDACTED]" in item.system_prompt
    assert "api_key" not in item.requirements
    assert item.expected_output["secret"] == "[REDACTED]"


def test_request_and_module_capture_opt_outs_are_respected(tmp_path: Path) -> None:
    _, queue, _, repository, service, _, run_id = _context(tmp_path)
    _completed_request(
        queue,
        run_id,
        idempotency_key="request-opt-out",
        requirements={"model_lab_capture": False},
    )
    service.update_settings(
        enabled=True,
        capture_enabled=True,
        excluded_modules=["synthetic"],
    )
    _completed_request(
        queue,
        run_id,
        module_id="synthetic",
        idempotency_key="module-opt-out",
        user_prompt="Synthetic benchmark candidate.",
    )

    assert service.harvest() == 0
    assert repository.corpus_count() == 0


def test_benchmark_replay_is_persistent_and_does_not_change_production_evidence(
    tmp_path: Path,
) -> None:
    _, queue, evidence, repository, service, _, run_id = _context(tmp_path)
    _completed_request(queue, run_id)
    service.harvest()
    corpus = repository.list_corpus()[0]
    evidence.record_outcome(
        task_id=corpus.task_id,
        provider="ollama",
        model="local-model",
        status="succeeded",
        duration_ms=100,
        schema_valid=True,
    )
    before = evidence.task_evidence(corpus.task_id)[0]
    exploration = service.start_exploration(duration_seconds=300, max_attempts=2)

    result = asyncio.run(
        service.replay(corpus.id, provider="ollama", model="local-model")
    )

    after = evidence.task_evidence(corpus.task_id)[0]
    assert result.status == "succeeded"
    assert result.schema_valid is True
    assert result.session_id == exploration.id
    assert before.attempts == after.attempts == 1
    assert len(repository.list_results()) == 1

    restarted_repository = ModelLabRepository(Database(Settings(data_dir=tmp_path)))
    restarted_repository.database.initialize()
    assert restarted_repository.corpus_count() == 1
    assert restarted_repository.list_results()[0].id == result.id


def test_exploration_budget_and_production_queue_block_replay(tmp_path: Path) -> None:
    _, queue, _, repository, service, _, run_id = _context(tmp_path)
    _completed_request(queue, run_id)
    service.harvest()
    corpus = repository.list_corpus()[0]
    service.start_exploration(duration_seconds=300, max_attempts=1)

    queue.submit(
        WorkRequestSpec(
            module_id="job_scout",
            run_id=run_id,
            task_id="job_scout.evaluate_fit",
            work_class=WorkClass.LLM,
            payload={"system_prompt": "system", "user_prompt": "production work"},
            output_contract={"type": "object"},
            idempotency_key="production-waiting",
            module_priority=100,
            task_priority=100,
        )
    )
    with pytest.raises(ModelLabBusyError):
        asyncio.run(service.replay(corpus.id, provider="ollama", model="local-model"))

    queued = next(
        item for item in queue.list_requests() if item.idempotency_key == "production-waiting"
    )
    queue.cancel(queued.id)
    asyncio.run(service.replay(corpus.id, provider="ollama", model="local-model"))
    with pytest.raises(ValueError):
        asyncio.run(service.replay(corpus.id, provider="ollama", model="local-model"))


def test_disabled_model_lab_does_not_change_normal_provider_routing(tmp_path: Path) -> None:
    _, _, _, _, service, manager, _ = _context(tmp_path)
    service.update_settings(enabled=False, capture_enabled=True, excluded_modules=[])

    with pytest.raises(ModelLabDisabledError):
        service.start_exploration(duration_seconds=60, max_attempts=1)

    normal = asyncio.run(
        manager.execute(
            ModelBlindRequest(
                task_id="normal.production.task",
                system_prompt="system",
                user_prompt="user",
                output_schema={"type": "object"},
                contract_version="production-v1",
            )
        )
    )
    assert normal.value == {"score": 92}


def test_model_lab_api_exposes_catalog_and_disabled_state(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path), provider=FakeJsonProvider())

    with TestClient(app) as client:
        overview = client.get("/api/v1/model-lab")
        assert overview.status_code == 200
        payload = overview.json()
        assert payload["models"][0]["model"] == "local-model"
        assert payload["corpus_count"] == 0
        disabled = client.put(
            "/api/v1/model-lab/settings",
            json={
                "enabled": False,
                "capture_enabled": True,
                "excluded_modules": [],
            },
        )
        assert disabled.status_code == 200
        blocked = client.post(
            "/api/v1/model-lab/sessions",
            json={"duration_seconds": 60, "max_attempts": 1},
        )
        assert blocked.status_code == 409
