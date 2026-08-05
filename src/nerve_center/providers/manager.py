"""Manager-owned model selection over provider-neutral task requirements."""

from __future__ import annotations

from time import perf_counter
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from nerve_center.persistence.providers import ModelEvidenceRepository, TaskModelEvidence
from nerve_center.providers.base import (
    JsonGenerationResult,
    JsonProvider,
    ModelBlindRequest,
    ProviderModel,
    StructuredGenerationResult,
)
from nerve_center.providers.errors import ProviderError

TResponse = TypeVar("TResponse", bound=BaseModel)


class ProviderManager:
    def __init__(
        self,
        providers: tuple[JsonProvider, ...],
        *,
        evidence: ModelEvidenceRepository | None = None,
    ) -> None:
        if not providers:
            raise ValueError("at least one provider is required")
        self.providers = providers
        self.evidence = evidence
        self._loaded_model: tuple[str, str] | None = None

    async def list_models(self) -> list[ProviderModel]:
        models: list[ProviderModel] = []
        for provider in self.providers:
            discovered = await provider.list_models()
            if self.evidence is not None:
                self.evidence.sync_models(provider.name, discovered)
            models.extend(discovered)
        return sorted(models, key=lambda item: item.id.casefold())

    async def execute(self, request: ModelBlindRequest) -> JsonGenerationResult:
        candidates = await self._ranked_candidates(request)
        last_error: ProviderError | None = None
        allow_fallback = request.requirements.get("fallback_policy", "alternate_model") != "none"
        for index, (provider, model) in enumerate(candidates):
            started = perf_counter()
            try:
                result = await provider.generate_json(
                    model=model.id,
                    system_prompt=request.system_prompt,
                    user_prompt=request.user_prompt,
                    output_schema=request.output_schema,
                    contract_version=request.contract_version,
                )
            except ProviderError as error:
                last_error = error
                if self.evidence is not None:
                    self.evidence.record_outcome(
                        task_id=request.task_id,
                        provider=provider.name,
                        model=model.id,
                        status="failed",
                        duration_ms=error.duration_ms
                        or round((perf_counter() - started) * 1000),
                        retry_count=error.retry_count,
                        provider_call_id=error.call_id,
                        work_request_id=request.request_id,
                        error_code=error.code,
                    )
                if not allow_fallback or index == len(candidates) - 1:
                    raise
                continue
            self._loaded_model = (provider.name, model.id)
            if self.evidence is not None:
                self.evidence.record_outcome(
                    task_id=request.task_id,
                    provider=result.metadata.provider,
                    model=result.metadata.model,
                    status=result.metadata.status,
                    duration_ms=result.metadata.duration_ms,
                    retry_count=result.metadata.retry_count,
                    provider_call_id=result.metadata.id,
                    work_request_id=request.request_id,
                )
            return result
        if last_error is not None:
            raise last_error
        raise ProviderError("manager", "NO_COMPATIBLE_MODEL", "No compatible model is installed.")

    async def generate_structured(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        response_type: type[TResponse],
        contract_version: str,
    ) -> StructuredGenerationResult[TResponse]:
        del model
        result = await self.execute(
            ModelBlindRequest(
                task_id=contract_version,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                output_schema=response_type.model_json_schema(),
                requirements={"structured_output": True},
                contract_version=contract_version,
            )
        )
        try:
            value = response_type.model_validate(result.value)
        except ValidationError as error:
            if self.evidence is not None:
                self.evidence.record_outcome(
                    task_id=contract_version,
                    provider=result.metadata.provider,
                    model=result.metadata.model,
                    status="failed",
                    duration_ms=result.metadata.duration_ms,
                    retry_count=result.metadata.retry_count,
                    provider_call_id=result.metadata.id,
                    schema_valid=False,
                    error_code="SCHEMA_VALIDATION_FAILED",
                )
            raise ProviderError(
                result.metadata.provider,
                "SCHEMA_VALIDATION_FAILED",
                "The selected model returned data outside the required contract.",
            ) from error
        if self.evidence is not None:
            self.evidence.record_outcome(
                task_id=contract_version,
                provider=result.metadata.provider,
                model=result.metadata.model,
                status="succeeded",
                duration_ms=result.metadata.duration_ms,
                retry_count=result.metadata.retry_count,
                provider_call_id=result.metadata.id,
                schema_valid=True,
            )
        return StructuredGenerationResult(value=value, metadata=result.metadata)

    async def select(self, request: ModelBlindRequest) -> tuple[JsonProvider, ProviderModel]:
        return (await self._ranked_candidates(request))[0]

    async def task_routing_scores(self, task_ids: set[str]) -> dict[str, float]:
        if not task_ids:
            return {}
        candidates = await self._discover_candidates()
        scores: dict[str, float] = {}
        for task_id in task_ids:
            evidence = {
                (item.provider, item.model): item
                for item in (
                    self.evidence.task_evidence(task_id)
                    if self.evidence is not None
                    else []
                )
            }
            scores[task_id] = max(
                self._suitability(provider.name, model.id, evidence)
                for provider, model in candidates
            ) * 10
        return scores

    async def _ranked_candidates(
        self, request: ModelBlindRequest
    ) -> list[tuple[JsonProvider, ProviderModel]]:
        modalities = request.requirements.get("modalities", ["text"])
        if modalities not in (None, ["text"], ("text",)):
            raise ProviderError(
                "manager",
                "NO_COMPATIBLE_MODEL",
                "No installed model supports the requested modalities.",
            )
        candidates = await self._discover_candidates()
        evidence = {
            (item.provider, item.model): item
            for item in (
                self.evidence.task_evidence(request.task_id)
                if self.evidence is not None
                else []
            )
        }
        return sorted(
            candidates,
            key=lambda item: (
                -self._suitability(item[0].name, item[1].id, evidence),
                item[0].name,
                item[1].id.casefold(),
            ),
        )

    async def _discover_candidates(self) -> list[tuple[JsonProvider, ProviderModel]]:
        candidates: list[tuple[JsonProvider, ProviderModel]] = []
        errors: list[ProviderError] = []
        for provider in self.providers:
            try:
                models = await provider.list_models()
                if self.evidence is not None:
                    self.evidence.sync_models(provider.name, models)
                candidates.extend((provider, model) for model in models)
            except ProviderError as error:
                errors.append(error)
        if not candidates:
            if errors:
                raise errors[0]
            raise ProviderError("manager", "NO_COMPATIBLE_MODEL", "No local model is installed.")
        return candidates

    def _suitability(
        self,
        provider: str,
        model: str,
        evidence: dict[tuple[str, str], TaskModelEvidence],
    ) -> float:
        observed = evidence.get((provider, model))
        score = 0.20 if observed is None else 0.0
        if observed is not None:
            score += observed.success_rate * 0.45
            score += observed.schema_valid_rate * 0.30
            score += (observed.acceptance_rate or 0.0) * 0.20
            if observed.average_duration_ms > 0:
                score += min(10_000 / observed.average_duration_ms, 1.0) * 0.05
        if self._loaded_model == (provider, model) and (
            observed is None or observed.success_rate >= 0.5
        ):
            score += 0.10
        return score
