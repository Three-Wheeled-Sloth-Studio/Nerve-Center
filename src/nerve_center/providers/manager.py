"""Manager-owned model selection over provider-neutral task requirements."""

from __future__ import annotations

import re
from time import perf_counter
from typing import TypeVar

from jsonschema import SchemaError, validate
from jsonschema import ValidationError as JsonSchemaValidationError
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
        preferred_model: str | None = None,
        schema_fallback_model: str | None = None,
        allow_model_fallback: bool = True,
    ) -> None:
        if not providers:
            raise ValueError("at least one provider is required")
        self.providers = providers
        self.evidence = evidence
        self.preferred_model = preferred_model.strip() if preferred_model else None
        self.schema_fallback_model = (
            schema_fallback_model.strip() if schema_fallback_model else None
        )
        self.allow_model_fallback = allow_model_fallback
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
        strict_schema = bool(request.requirements.get("structured_output", request.output_schema))
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
                self._record_failure(request, provider.name, model.id, started, error)
                if not allow_fallback or index == len(candidates) - 1:
                    raise
                continue
            if strict_schema:
                try:
                    validate(result.value, request.output_schema)
                except (SchemaError, JsonSchemaValidationError) as validation_error:
                    last_error = ProviderError(
                        result.metadata.provider,
                        "SCHEMA_VALIDATION_FAILED",
                        "The selected model returned data outside the required contract.",
                    )
                    last_error.call_id = result.metadata.id
                    last_error.duration_ms = result.metadata.duration_ms
                    self._record_failure(
                        request,
                        result.metadata.provider,
                        result.metadata.model,
                        started,
                        last_error,
                        schema_valid=False,
                    )
                    if not allow_fallback or index == len(candidates) - 1:
                        raise last_error from validation_error
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

    async def execute_specific(
        self,
        request: ModelBlindRequest,
        *,
        provider_name: str,
        model_id: str,
    ) -> JsonGenerationResult:
        """Run an explicitly selected manager experiment without production routing evidence."""

        candidates = await self._discover_candidates()
        selected = next(
            (
                (provider, model)
                for provider, model in candidates
                if provider.name == provider_name and model.id == model_id
            ),
            None,
        )
        if selected is None:
            raise ProviderError(
                provider_name,
                "MODEL_UNAVAILABLE",
                f"Model {provider_name}/{model_id} is not installed.",
            )
        provider, model = selected
        return await provider.generate_json(
            model=model.id,
            system_prompt=request.system_prompt,
            user_prompt=request.user_prompt,
            output_schema=request.output_schema,
            contract_version=request.contract_version,
        )

    def _record_failure(
        self,
        request: ModelBlindRequest,
        provider: str,
        model: str,
        started: float,
        error: ProviderError,
        *,
        schema_valid: bool | None = None,
    ) -> None:
        if self.evidence is None:
            return
        self.evidence.record_outcome(
            task_id=request.task_id,
            provider=provider,
            model=model,
            status="failed",
            duration_ms=error.duration_ms or round((perf_counter() - started) * 1000),
            retry_count=error.retry_count,
            provider_call_id=error.call_id,
            work_request_id=request.request_id,
            schema_valid=schema_valid,
            error_code=error.code,
        )

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
                self._suitability(provider.name, model, evidence, task_id=task_id)
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
        if self.preferred_model and not self.allow_model_fallback:
            preferred = [item for item in candidates if item[1].id == self.preferred_model]
            if not preferred:
                raise ProviderError(
                    "manager",
                    "PREFERRED_MODEL_UNAVAILABLE",
                    (
                        f"Preferred model {self.preferred_model!r} is not available among "
                        "discovered local models and fallback is disabled."
                    ),
                )
            candidates = preferred
        strict_schema = bool(request.requirements.get("structured_output", request.output_schema))
        if strict_schema and self.allow_model_fallback and self.preferred_model:
            configured_lane = [
                item
                for item in candidates
                if item[1].id in {self.preferred_model, self.schema_fallback_model}
            ]
            if any(item[1].id == self.preferred_model for item in configured_lane):
                candidates = configured_lane
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
                0
                if item[1].id == self.preferred_model
                else 1
                if strict_schema and item[1].id == self.schema_fallback_model
                else 2,
                -self._suitability(
                    item[0].name,
                    item[1],
                    evidence,
                    task_id=request.task_id,
                    requirements=request.requirements,
                ),
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
        model: ProviderModel,
        evidence: dict[tuple[str, str], TaskModelEvidence],
        *,
        task_id: str,
        requirements: dict[str, object] | None = None,
    ) -> float:
        observed = evidence.get((provider, model.id))
        score = _cold_start_prior(model, task_id, requirements or {}) if observed is None else 0.0
        if observed is not None:
            score += observed.success_rate * 0.45
            score += observed.schema_valid_rate * 0.30
            score += (observed.acceptance_rate or 0.0) * 0.20
            if observed.average_duration_ms > 0:
                score += min(10_000 / observed.average_duration_ms, 1.0) * 0.05
        if self._loaded_model == (provider, model.id) and (
            observed is None or observed.success_rate >= 0.5
        ):
            score += 0.10
        if model.id == self.preferred_model:
            score += 1.0
        return score


def _cold_start_prior(
    model: ProviderModel,
    task_id: str,
    requirements: dict[str, object],
) -> float:
    """Prefer plausible local task fits until real task evidence takes over.

    The prior is intentionally bounded below one successful empirical observation.
    It uses provider metadata only; it does not claim measured quality or hardware fit.
    """

    score = 0.20
    parameters = _parameter_billions(model.parameter_size)
    quality_tier = str(requirements.get("quality_tier") or "balanced").casefold()
    if parameters is not None:
        if parameters < 2:
            score += 0.01
        elif parameters < 5:
            score += 0.06
        elif parameters <= 14:
            score += 0.15
        elif parameters <= 35:
            score += 0.17 if quality_tier in {"high", "premium"} else 0.12
        else:
            score += 0.10 if quality_tier in {"high", "premium"} else 0.06

    identity = " ".join(filter(None, (model.id, model.family))).casefold()
    coding_task = any(token in task_id.casefold() for token in ("code", "program", "sql"))
    image_task = "image" in task_id.casefold() or "vision" in task_id.casefold()
    if "coder" in identity and not coding_task:
        score -= 0.06
    if ("-vl" in identity or "vision" in identity) and not image_task:
        score -= 0.05
    if "instruct" in identity:
        score += 0.02
    if model.size_bytes is not None and model.size_bytes < 1_000_000:
        score -= 0.15
    return max(score, 0.0)


def _parameter_billions(value: str | None) -> float | None:
    if not value:
        return None
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*([bm])", value.casefold())
    if match is None:
        return None
    amount = float(match.group(1))
    return amount if match.group(2) == "b" else amount / 1000
