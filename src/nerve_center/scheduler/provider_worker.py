"""Provider-neutral executor for durable model-blind queue requests."""

from __future__ import annotations

from typing import Any

from jsonschema import SchemaError, ValidationError, validate

from nerve_center.domain.work_queue import (
    WorkClass,
    WorkRequestSnapshot,
    WorkRequestStatus,
)
from nerve_center.providers.base import ModelBlindRequest
from nerve_center.providers.errors import ProviderError
from nerve_center.providers.manager import ProviderManager
from nerve_center.scheduler.work_queue import WorkQueueService


class ProviderWorkExecutor:
    def __init__(
        self,
        queue: WorkQueueService,
        providers: ProviderManager,
        *,
        worker_id: str = "core.provider",
    ) -> None:
        self.queue = queue
        self.providers = providers
        self.worker_id = worker_id

    async def tick(self) -> WorkRequestSnapshot | None:
        queued = self.queue.list_requests(status=WorkRequestStatus.QUEUED, limit=1000)
        task_ids = {
            item.task_id for item in queued if item.work_class is WorkClass.LLM
        }
        try:
            routing_scores = await self.providers.task_routing_scores(task_ids)
        except ProviderError:
            routing_scores = {}
        attempt = self.queue.claim_next(
            self.worker_id,
            (WorkClass.LLM,),
            routing_scores=routing_scores,
        )
        if attempt is None:
            return None
        request = self.queue.get(attempt.request_id)
        generated = None
        try:
            model_request = _model_request(request)
            generated = await self.providers.execute(model_request)
            validate(generated.value, model_request.output_schema)
            if self.providers.evidence is not None:
                self.providers.evidence.record_outcome(
                    task_id=request.task_id,
                    provider=generated.metadata.provider,
                    model=generated.metadata.model,
                    status="succeeded",
                    duration_ms=generated.metadata.duration_ms,
                    retry_count=generated.metadata.retry_count,
                    provider_call_id=generated.metadata.id,
                    work_request_id=request.id,
                    schema_valid=True,
                )
            self.queue.complete(
                attempt.id,
                {
                    "value": generated.value,
                    "manager": {
                        "provider_call_id": generated.metadata.id,
                        "provider": generated.metadata.provider,
                        "model": generated.metadata.model,
                        "duration_ms": generated.metadata.duration_ms,
                        "retry_count": generated.metadata.retry_count,
                        "schema_valid": True,
                    },
                },
            )
        except ProviderError as error:
            return self.queue.fail(
                attempt.id,
                error.code,
                detail={"message": str(error), "provider": error.provider},
                retry_delay_seconds=1 if error.retryable else 0,
            )
        except (SchemaError, ValidationError) as error:
            if generated is not None and self.providers.evidence is not None:
                self.providers.evidence.record_outcome(
                    task_id=request.task_id,
                    provider=generated.metadata.provider,
                    model=generated.metadata.model,
                    status="failed",
                    duration_ms=generated.metadata.duration_ms,
                    retry_count=generated.metadata.retry_count,
                    provider_call_id=generated.metadata.id,
                    work_request_id=request.id,
                    schema_valid=False,
                    error_code="SCHEMA_VALIDATION_FAILED",
                )
            return self.queue.fail(
                attempt.id,
                "SCHEMA_VALIDATION_FAILED",
                detail={"message": error.message},
            )
        except (KeyError, TypeError, ValueError) as error:
            return self.queue.fail(
                attempt.id,
                "INVALID_MODEL_REQUEST",
                detail={"message": str(error)},
            )
        return self.queue.get(request.id)


def _model_request(request: WorkRequestSnapshot) -> ModelBlindRequest:
    system_prompt = request.payload.get("system_prompt")
    user_prompt = request.payload.get("user_prompt")
    if not isinstance(system_prompt, str) or not system_prompt.strip():
        raise ValueError("system_prompt is required")
    if not isinstance(user_prompt, str) or not user_prompt.strip():
        raise ValueError("user_prompt is required")
    if not request.output_contract:
        raise ValueError("output_contract is required")
    requirements: dict[str, Any] = dict(request.requirements)
    requirements.setdefault("structured_output", True)
    return ModelBlindRequest(
        task_id=request.task_id,
        request_id=request.id,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        output_schema=request.output_contract,
        requirements=requirements,
        contract_version=str(requirements.get("contract_version") or request.task_id),
    )
