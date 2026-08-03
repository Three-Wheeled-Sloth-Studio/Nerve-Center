"""Local Ollama structured-output provider."""

from __future__ import annotations

import asyncio
import json
from contextlib import suppress
from datetime import datetime
from time import perf_counter
from typing import Any
from uuid import uuid4

import httpx
from pydantic import BaseModel, ValidationError

from nerve_center.providers.base import (
    NullProviderTelemetry,
    ProviderCallMetadata,
    ProviderModel,
    ProviderTelemetry,
    StructuredGenerationResult,
    TResponse,
)
from nerve_center.providers.errors import ProviderError


class OllamaProvider:
    name = "ollama"

    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:11434",
        timeout_seconds: float = 180.0,
        telemetry: ProviderTelemetry | None = None,
        client: httpx.AsyncClient | None = None,
        max_retries: int = 1,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.telemetry = telemetry or NullProviderTelemetry()
        self.max_retries = max_retries
        self._client = client

    async def list_models(self) -> list[ProviderModel]:
        response = await self._send("GET", "/api/tags")
        payload = self._json_object(response)
        models = payload.get("models", [])
        if not isinstance(models, list):
            raise ProviderError(
                self.name,
                "INVALID_RESPONSE",
                "Ollama returned an invalid model list.",
            )

        result: list[ProviderModel] = []
        for item in models:
            if not isinstance(item, dict):
                continue
            model_id = str(item.get("model") or item.get("name") or "").strip()
            if not model_id:
                continue
            details = item.get("details") if isinstance(item.get("details"), dict) else {}
            modified_at = _parse_datetime(item.get("modified_at"))
            result.append(
                ProviderModel(
                    id=model_id,
                    label=str(item.get("name") or model_id),
                    family=_optional_string(details.get("family")),
                    parameter_size=_optional_string(details.get("parameter_size")),
                    quantization=_optional_string(details.get("quantization_level")),
                    modified_at=modified_at,
                )
            )
        return result

    async def generate_structured(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        response_type: type[TResponse],
        contract_version: str,
    ) -> StructuredGenerationResult[TResponse]:
        request_id = str(uuid4())
        started = perf_counter()
        started_at = datetime.now().astimezone()
        retry_count = 0
        output_text = ""
        status = "failed"
        error_code: str | None = None
        prompt_eval_count: int | None = None
        eval_count: int | None = None

        schema = response_type.model_json_schema()
        grounded_prompt = (
            f"{user_prompt.rstrip()}\n\n"
            "Return only data matching this JSON schema:\n"
            f"{json.dumps(schema, separators=(',', ':'), ensure_ascii=True)}"
        )
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": grounded_prompt},
            ],
            "stream": False,
            "format": schema,
            "options": {"temperature": 0},
        }

        try:
            response, retry_count = await self._send_with_retries("POST", "/api/chat", json=body)
            payload = self._json_object(response)
            message = payload.get("message")
            if not isinstance(message, dict) or not isinstance(message.get("content"), str):
                raise ProviderError(
                    self.name,
                    "INVALID_RESPONSE",
                    "Ollama returned a response without structured content.",
                )
            output_text = message["content"]
            prompt_eval_count = _optional_int(payload.get("prompt_eval_count"))
            eval_count = _optional_int(payload.get("eval_count"))
            try:
                value = response_type.model_validate_json(output_text)
            except ValidationError as error:
                raise ProviderError(
                    self.name,
                    "SCHEMA_VALIDATION_FAILED",
                    "Ollama returned content that did not match the required schema.",
                ) from error
            status = "succeeded"
            metadata = self._metadata(
                request_id=request_id,
                model=model,
                contract_version=contract_version,
                response_type=response_type,
                started_at=started_at,
                started=started,
                status=status,
                error_code=None,
                retry_count=retry_count,
                input_char_count=len(system_prompt) + len(grounded_prompt),
                output_char_count=len(output_text),
                prompt_eval_count=prompt_eval_count,
                eval_count=eval_count,
            )
            self.telemetry.record(metadata)
            return StructuredGenerationResult(value=value, metadata=metadata)
        except ProviderError as error:
            error_code = error.code
            raise
        finally:
            if status != "succeeded":
                self.telemetry.record(
                    self._metadata(
                        request_id=request_id,
                        model=model,
                        contract_version=contract_version,
                        response_type=response_type,
                        started_at=started_at,
                        started=started,
                        status="failed",
                        error_code=error_code or "UNKNOWN_PROVIDER_ERROR",
                        retry_count=retry_count,
                        input_char_count=len(system_prompt) + len(grounded_prompt),
                        output_char_count=len(output_text),
                        prompt_eval_count=prompt_eval_count,
                        eval_count=eval_count,
                    )
                )

    async def _send_with_retries(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> tuple[httpx.Response, int]:
        retries = 0
        while True:
            try:
                return await self._send(method, path, **kwargs), retries
            except ProviderError as error:
                if not error.retryable or retries >= self.max_retries:
                    raise
                retries += 1
                await asyncio.sleep(0.2 * retries)

    async def _send(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        client = self._client
        owns_client = client is None
        if client is None:
            client = httpx.AsyncClient(timeout=self.timeout_seconds)
        try:
            response = await client.request(method, f"{self.base_url}{path}", **kwargs)
        except httpx.TimeoutException as error:
            raise ProviderError(
                self.name,
                "PROVIDER_TIMEOUT",
                "Ollama did not respond before the local timeout.",
                retryable=True,
            ) from error
        except httpx.RequestError as error:
            raise ProviderError(
                self.name,
                "OLLAMA_UNREACHABLE",
                "Ollama is not reachable. Make sure the local service is running.",
                retryable=True,
            ) from error
        finally:
            if owns_client:
                await client.aclose()

        if response.status_code >= 400:
            retryable = response.status_code == 429 or response.status_code >= 500
            message = "Ollama rejected the request."
            with suppress(ValueError):
                payload = response.json()
                if isinstance(payload, dict) and isinstance(payload.get("error"), str):
                    message = payload["error"][:500]
            raise ProviderError(
                self.name,
                "OLLAMA_HTTP_ERROR",
                message,
                retryable=retryable,
                status_code=response.status_code,
            )
        return response

    def _json_object(self, response: httpx.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as error:
            raise ProviderError(
                self.name,
                "INVALID_RESPONSE",
                "Ollama returned invalid JSON.",
            ) from error
        if not isinstance(payload, dict):
            raise ProviderError(self.name, "INVALID_RESPONSE", "Ollama returned invalid JSON.")
        return payload

    def _metadata(
        self,
        *,
        request_id: str,
        model: str,
        contract_version: str,
        response_type: type[BaseModel],
        started_at: datetime,
        started: float,
        status: str,
        error_code: str | None,
        retry_count: int,
        input_char_count: int,
        output_char_count: int,
        prompt_eval_count: int | None,
        eval_count: int | None,
    ) -> ProviderCallMetadata:
        return ProviderCallMetadata(
            id=request_id,
            provider=self.name,
            model=model,
            contract_version=contract_version,
            response_schema=response_type.__name__,
            started_at=started_at,
            duration_ms=max(0, round((perf_counter() - started) * 1000)),
            status=status,
            error_code=error_code,
            retry_count=retry_count,
            input_char_count=input_char_count,
            output_char_count=output_char_count,
            prompt_eval_count=prompt_eval_count,
            eval_count=eval_count,
        )


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _optional_string(value: object) -> str | None:
    return str(value) if value not in (None, "") else None


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) else None
