"""Provider-neutral structured generation contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Generic, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

TResponse = TypeVar("TResponse", bound=BaseModel)


class ProviderModel(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    label: str
    family: str | None = None
    parameter_size: str | None = None
    quantization: str | None = None
    size_bytes: int | None = Field(default=None, ge=0)
    modified_at: datetime | None = None


class ProviderCallMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    provider: str
    model: str
    contract_version: str
    response_schema: str
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    duration_ms: int
    status: str
    error_code: str | None = None
    retry_count: int = 0
    input_char_count: int = 0
    output_char_count: int = 0
    prompt_eval_count: int | None = None
    eval_count: int | None = None


class StructuredGenerationResult(BaseModel, Generic[TResponse]):
    value: TResponse
    metadata: ProviderCallMetadata


class JsonGenerationResult(BaseModel):
    value: dict[str, Any] | list[Any]
    metadata: ProviderCallMetadata


class ModelBlindRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    task_id: str
    request_id: str | None = None
    system_prompt: str
    user_prompt: str
    output_schema: dict[str, Any]
    requirements: dict[str, Any] = Field(default_factory=dict)
    contract_version: str


class ProviderTelemetry(Protocol):
    def record(self, metadata: ProviderCallMetadata) -> None: ...


class NullProviderTelemetry:
    def record(self, metadata: ProviderCallMetadata) -> None:
        del metadata


class StructuredProvider(Protocol):
    name: str

    async def list_models(self) -> list[ProviderModel]: ...

    async def generate_structured(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        response_type: type[TResponse],
        contract_version: str,
    ) -> StructuredGenerationResult[TResponse]: ...


@runtime_checkable
class JsonProvider(Protocol):
    name: str

    async def list_models(self) -> list[ProviderModel]: ...

    async def generate_json(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        output_schema: dict[str, Any],
        contract_version: str,
    ) -> JsonGenerationResult: ...
