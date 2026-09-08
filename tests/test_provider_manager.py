import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from nerve_center.api.app import create_app
from nerve_center.config import Settings
from nerve_center.domain.run_window import DurationRunWindow
from nerve_center.domain.work_queue import WorkClass, WorkRequestSpec, WorkRequestStatus
from nerve_center.persistence.database import Database
from nerve_center.persistence.providers import ModelEvidenceRepository
from nerve_center.persistence.runs import RunRepository
from nerve_center.persistence.work_queue import WorkQueueRepository
from nerve_center.providers.base import (
    JsonGenerationResult,
    ModelBlindRequest,
    ProviderCallMetadata,
    ProviderModel,
)
from nerve_center.providers.errors import ProviderError
from nerve_center.providers.manager import ProviderManager
from nerve_center.scheduler.provider_worker import ProviderWorkExecutor
from nerve_center.scheduler.work_queue import WorkQueueService


class FakeJsonProvider:
    def __init__(self, name: str, model: str, value: dict[str, Any]) -> None:
        self.name = name
        self.model = model
        self.value = value
        self.selected_models: list[str] = []

    async def list_models(self) -> list[ProviderModel]:
        return [ProviderModel(id=self.model, label=self.model)]

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
                id=f"call-{model}",
                provider=self.name,
                model=model,
                contract_version=contract_version,
                response_schema="json_schema",
                started_at=datetime.now(UTC),
                duration_ms=25,
                status="succeeded",
            ),
        )


class FailingJsonProvider(FakeJsonProvider):
    async def generate_json(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        output_schema: dict[str, Any],
        contract_version: str,
    ) -> JsonGenerationResult:
        del model, system_prompt, user_prompt, output_schema, contract_version
        raise ProviderError(self.name, "MODEL_FAILED", "The model failed.")


class MetadataFakeProvider(FakeJsonProvider):
    def __init__(self, model: ProviderModel, value: dict[str, Any]) -> None:
        super().__init__("ollama", model.id, value)
        self.metadata = model

    async def list_models(self) -> list[ProviderModel]:
        return [self.metadata]


def make_queue(tmp_path: Path) -> tuple[WorkQueueService, str]:
    database = Database(Settings(data_dir=tmp_path))
    database.initialize()
    run = RunRepository(database).create(
        "job_scout.discovery", DurationRunWindow(timedelta(minutes=5))
    )
    return WorkQueueService(WorkQueueRepository(database)), run.id


def model_request() -> ModelBlindRequest:
    return ModelBlindRequest(
        task_id="job_scout.evaluate_fit",
        system_prompt="Use only supplied evidence.",
        user_prompt="Evaluate this job.",
        output_schema={
            "type": "object",
            "properties": {"score": {"type": "integer"}},
            "required": ["score"],
        },
        contract_version="fit-v1",
    )


def test_manager_selects_model_without_request_naming_one() -> None:
    later = FakeJsonProvider("ollama", "z-model", {"score": 80})
    first = FakeJsonProvider("ollama", "a-model", {"score": 90})
    manager = ProviderManager((later, first))

    result = asyncio.run(manager.execute(model_request()))

    assert result.value == {"score": 90}
    assert first.selected_models == ["a-model"]
    assert later.selected_models == []


def test_manager_uses_metadata_prior_instead_of_alphabetical_cold_start() -> None:
    tiny = MetadataFakeProvider(
        ProviderModel(
            id="a-tiny",
            label="a-tiny",
            family="gemma3",
            parameter_size="999.89M",
            size_bytes=815_000_000,
        ),
        {"score": 60},
    )
    balanced = MetadataFakeProvider(
        ProviderModel(
            id="z-instruct",
            label="z-instruct",
            family="qwen2",
            parameter_size="7.6B",
            size_bytes=4_700_000_000,
        ),
        {"score": 90},
    )
    manager = ProviderManager((tiny, balanced))

    result = asyncio.run(manager.execute(model_request()))

    assert result.value == {"score": 90}
    assert balanced.selected_models == ["z-instruct"]
    assert tiny.selected_models == []


def test_manager_honors_manager_owned_preferred_model() -> None:
    alternate = FakeJsonProvider("ollama", "larger-model", {"score": 70})
    preferred = FakeJsonProvider("ollama", "gemma3:4b", {"score": 90})
    manager = ProviderManager(
        (alternate, preferred),
        preferred_model="gemma3:4b",
    )

    result = asyncio.run(manager.execute(model_request()))

    assert result.value == {"score": 90}
    assert preferred.selected_models == ["gemma3:4b"]
    assert alternate.selected_models == []


def test_manager_can_bound_execution_to_manager_owned_preferred_model() -> None:
    preferred = FailingJsonProvider("ollama", "gemma3:4b", {})
    alternate = FakeJsonProvider("ollama", "alternate", {"score": 70})
    manager = ProviderManager(
        (preferred, alternate),
        preferred_model="gemma3:4b",
        allow_model_fallback=False,
    )

    with pytest.raises(ProviderError):
        asyncio.run(manager.execute(model_request()))

    assert alternate.selected_models == []


def test_manager_rejects_missing_preferred_model_when_fallback_disabled() -> None:
    alternate = FakeJsonProvider("ollama", "alternate", {"score": 70})
    manager = ProviderManager(
        (alternate,),
        preferred_model="gemma3:4b",
        allow_model_fallback=False,
    )

    with pytest.raises(ProviderError) as caught:
        asyncio.run(manager.execute(model_request()))

    assert caught.value.code == "PREFERRED_MODEL_UNAVAILABLE"
    assert alternate.selected_models == []


def test_strict_schema_failure_uses_configured_fallback_then_returns_to_primary() -> None:
    preferred = FakeJsonProvider("ollama", "gemma3:4b", {"score": "bad"})
    schema_fallback = FakeJsonProvider(
        "ollama", "qwen2.5:7b-instruct", {"score": 92}
    )
    unrelated = FakeJsonProvider("ollama", "another-model", {"score": 99})
    manager = ProviderManager(
        (unrelated, schema_fallback, preferred),
        preferred_model="gemma3:4b",
        schema_fallback_model="qwen2.5:7b-instruct",
    )

    strict_result = asyncio.run(manager.execute(model_request()))
    general_request = model_request().model_copy(
        update={"requirements": {"structured_output": False}}
    )
    general_result = asyncio.run(manager.execute(general_request))

    assert strict_result.value == {"score": 92}
    assert strict_result.metadata.model == "qwen2.5:7b-instruct"
    assert general_result.metadata.model == "gemma3:4b"
    assert preferred.selected_models == ["gemma3:4b", "gemma3:4b"]
    assert schema_fallback.selected_models == ["qwen2.5:7b-instruct"]
    assert unrelated.selected_models == []


def test_provider_executor_completes_valid_model_blind_work(tmp_path: Path) -> None:
    queue, run_id = make_queue(tmp_path)
    request = queue.submit(_queue_spec(run_id))
    executor = ProviderWorkExecutor(
        queue,
        ProviderManager((FakeJsonProvider("ollama", "local", {"score": 91}),)),
    )

    final = asyncio.run(executor.tick())
    delivered = queue.deliver_results("job_scout")

    assert final is not None
    assert final.status == WorkRequestStatus.AWAITING_ACKNOWLEDGEMENT
    assert delivered[0].request_id == request.id
    assert delivered[0].payload["value"] == {"score": 91}
    assert delivered[0].payload["manager"]["schema_valid"] is True


def test_provider_executor_rejects_schema_invalid_result(tmp_path: Path) -> None:
    queue, run_id = make_queue(tmp_path)
    request = queue.submit(_queue_spec(run_id, max_retries=0))
    executor = ProviderWorkExecutor(
        queue,
        ProviderManager((FakeJsonProvider("ollama", "local", {"score": "bad"}),)),
    )

    final = asyncio.run(executor.tick())

    assert final is not None
    assert final.id == request.id
    assert final.status == WorkRequestStatus.FAILED
    assert final.error_code == "SCHEMA_VALIDATION_FAILED"
    assert queue.deliver_results("job_scout") == []


def test_manager_prefers_task_model_with_stronger_observed_results(tmp_path: Path) -> None:
    database = Database(Settings(data_dir=tmp_path))
    database.initialize()
    evidence = ModelEvidenceRepository(database)
    evidence.record_outcome(
        task_id="job_scout.evaluate_fit",
        provider="ollama",
        model="b-model",
        status="succeeded",
        duration_ms=100,
        schema_valid=True,
    )
    first = FakeJsonProvider("ollama", "a-model", {"score": 70})
    stronger = FakeJsonProvider("ollama", "b-model", {"score": 95})
    manager = ProviderManager((first, stronger), evidence=evidence)

    result = asyncio.run(manager.execute(model_request()))

    assert result.value == {"score": 95}
    assert stronger.selected_models == ["b-model"]


def test_manager_falls_back_without_exposing_models_to_request() -> None:
    failing = FailingJsonProvider("ollama", "a-model", {})
    fallback = FakeJsonProvider("ollama", "b-model", {"score": 88})
    manager = ProviderManager((failing, fallback))

    result = asyncio.run(manager.execute(model_request()))

    assert result.value == {"score": 88}
    assert fallback.selected_models == ["b-model"]


def test_module_acknowledgement_records_acceptance_evidence(tmp_path: Path) -> None:
    database = Database(Settings(data_dir=tmp_path))
    database.initialize()
    evidence = ModelEvidenceRepository(database)
    run = RunRepository(database).create(
        "job_scout.discovery", DurationRunWindow(timedelta(minutes=5))
    )
    queue = WorkQueueService(WorkQueueRepository(database), model_evidence=evidence)
    request = queue.submit(_queue_spec(run.id))
    executor = ProviderWorkExecutor(
        queue,
        ProviderManager(
            (FakeJsonProvider("ollama", "local", {"score": 91}),),
            evidence=evidence,
        ),
    )

    asyncio.run(executor.tick())
    result = queue.deliver_results("job_scout")[0]
    queue.acknowledge(result.id, "job_scout", accepted=True)
    observed = evidence.task_evidence(request.task_id)

    assert observed[0].schema_valid_rate == 1.0
    assert observed[0].acceptance_rate == 1.0


def test_schema_failure_falls_back_within_the_same_queue_attempt(tmp_path: Path) -> None:
    database = Database(Settings(data_dir=tmp_path))
    database.initialize()
    evidence = ModelEvidenceRepository(database)
    run = RunRepository(database).create(
        "job_scout.discovery", DurationRunWindow(timedelta(minutes=5))
    )
    queue = WorkQueueService(WorkQueueRepository(database), model_evidence=evidence)
    queue.submit(_queue_spec(run.id, max_retries=1))
    invalid = FakeJsonProvider("ollama", "a-model", {"score": "bad"})
    valid = FakeJsonProvider("ollama", "b-model", {"score": 90})
    executor = ProviderWorkExecutor(
        queue, ProviderManager((invalid, valid), evidence=evidence)
    )

    first = asyncio.run(executor.tick())

    assert first is not None
    assert first.status == WorkRequestStatus.AWAITING_ACKNOWLEDGEMENT
    assert invalid.selected_models == ["a-model"]
    assert valid.selected_models == ["b-model"]


def test_provider_catalog_is_inspectable_without_exposing_routing_control(
    tmp_path: Path,
) -> None:
    provider = FakeJsonProvider("ollama", "local-model", {"score": 90})
    app = create_app(Settings(data_dir=tmp_path), provider=provider)

    with TestClient(app) as client:
        response = client.get("/api/v1/providers/models")

    assert response.status_code == 200
    assert response.json()[0]["model"] == "local-model"
    assert response.json()[0]["hardware_fit"]["status"] == "observed"


def _queue_spec(run_id: str, *, max_retries: int = 2) -> WorkRequestSpec:
    request = model_request()
    return WorkRequestSpec(
        module_id="job_scout",
        run_id=run_id,
        task_id=request.task_id,
        work_class=WorkClass.LLM,
        payload={
            "system_prompt": request.system_prompt,
            "user_prompt": request.user_prompt,
        },
        output_contract=request.output_schema,
        requirements={"contract_version": request.contract_version},
        idempotency_key="fit-job-1",
        module_priority=100,
        task_priority=70,
        max_retries=max_retries,
    )
