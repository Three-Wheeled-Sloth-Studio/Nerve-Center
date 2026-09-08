"""Local Ollama structured-output provider."""

from __future__ import annotations

import asyncio
import json
from contextlib import suppress
from datetime import UTC, datetime
from time import perf_counter
from typing import Any
from uuid import uuid4

import httpx
from pydantic import BaseModel, ValidationError

from nerve_center.providers.base import (
    JsonGenerationResult,
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
                    size_bytes=_optional_int(item.get("size")),
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
        started_at = datetime.now(UTC)
        retry_count = 0
        output_text = ""
        status = "failed"
        error_code: str | None = None
        prompt_eval_count: int | None = None
        eval_count: int | None = None

        schema = _ollama_schema(response_type.model_json_schema())
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
            while True:
                try:
                    response = await self._send("POST", "/api/chat", json=body)
                except ProviderError as error:
                    if not error.retryable or retry_count >= self.max_retries:
                        raise
                    retry_count += 1
                    await asyncio.sleep(0.2 * retry_count)
                    continue
                payload = self._json_object(response)
                message = payload.get("message")
                if not isinstance(message, dict) or not isinstance(message.get("content"), str):
                    error = ProviderError(
                        self.name,
                        "INVALID_RESPONSE",
                        "Ollama returned a response without structured content.",
                    )
                else:
                    output_text = message["content"]
                    prompt_eval_count = _optional_int(payload.get("prompt_eval_count"))
                    eval_count = _optional_int(payload.get("eval_count"))
                    try:
                        value = response_type.model_validate(_decode_json_output(output_text))
                        break
                    except (ValidationError, ValueError) as validation_error:
                        error = ProviderError(
                            self.name,
                            "SCHEMA_VALIDATION_FAILED",
                            "Ollama returned content that did not match the required schema.",
                        )
                        error.__cause__ = validation_error
                if retry_count >= self.max_retries:
                    raise error
                retry_count += 1
                body = _repair_body(body, output_text)
                await asyncio.sleep(0.2 * retry_count)
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
            error.call_id = request_id
            error.model = model
            error.duration_ms = max(0, round((perf_counter() - started) * 1000))
            error.retry_count = retry_count
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

    async def generate_json(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        output_schema: dict[str, Any],
        contract_version: str,
    ) -> JsonGenerationResult:
        request_id = str(uuid4())
        started = perf_counter()
        started_at = datetime.now(UTC)
        retry_count = 0
        output_text = ""
        status = "failed"
        error_code: str | None = None
        prompt_eval_count: int | None = None
        eval_count: int | None = None
        compatible_schema = _ollama_schema(output_schema)
        grounded_prompt = (
            f"{user_prompt.rstrip()}\n\n"
            "Return only data matching this JSON schema:\n"
            f"{json.dumps(compatible_schema, separators=(',', ':'), ensure_ascii=True)}"
        )
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": grounded_prompt},
            ],
            "stream": False,
            "format": compatible_schema,
            "options": {"temperature": 0},
        }
        try:
            while True:
                try:
                    response = await self._send("POST", "/api/chat", json=body)
                except ProviderError as error:
                    if not error.retryable or retry_count >= self.max_retries:
                        raise
                    retry_count += 1
                    await asyncio.sleep(0.2 * retry_count)
                    continue
                payload = self._json_object(response)
                message = payload.get("message")
                if not isinstance(message, dict) or not isinstance(message.get("content"), str):
                    error = ProviderError(
                        self.name,
                        "INVALID_RESPONSE",
                        "Ollama returned a response without structured content.",
                    )
                else:
                    output_text = message["content"]
                    prompt_eval_count = _optional_int(payload.get("prompt_eval_count"))
                    eval_count = _optional_int(payload.get("eval_count"))
                    try:
                        value = _decode_json_output(output_text)
                    except ValueError as decode_error:
                        error = ProviderError(
                            self.name,
                            "INVALID_RESPONSE",
                            "Ollama returned invalid structured JSON.",
                        )
                        error.__cause__ = decode_error
                    else:
                        if isinstance(value, (dict, list)):
                            break
                        error = ProviderError(
                            self.name,
                            "INVALID_RESPONSE",
                            "Ollama returned a scalar instead of structured JSON.",
                        )
                if retry_count >= self.max_retries:
                    raise error
                retry_count += 1
                body = _repair_body(body, output_text)
                await asyncio.sleep(0.2 * retry_count)
            status = "succeeded"
            metadata = ProviderCallMetadata(
                id=request_id,
                provider=self.name,
                model=model,
                contract_version=contract_version,
                response_schema="json_schema",
                started_at=started_at,
                duration_ms=max(0, round((perf_counter() - started) * 1000)),
                status=status,
                retry_count=retry_count,
                input_char_count=len(system_prompt) + len(grounded_prompt),
                output_char_count=len(output_text),
                prompt_eval_count=prompt_eval_count,
                eval_count=eval_count,
            )
            self.telemetry.record(metadata)
            return JsonGenerationResult(value=value, metadata=metadata)
        except ProviderError as error:
            error_code = error.code
            error.call_id = request_id
            error.model = model
            error.duration_ms = max(0, round((perf_counter() - started) * 1000))
            error.retry_count = retry_count
            raise
        finally:
            if status != "succeeded":
                self.telemetry.record(
                    ProviderCallMetadata(
                        id=request_id,
                        provider=self.name,
                        model=model,
                        contract_version=contract_version,
                        response_schema="json_schema",
                        started_at=started_at,
                        duration_ms=max(0, round((perf_counter() - started) * 1000)),
                        status="failed",
                        error_code=error_code or "UNKNOWN_PROVIDER_ERROR",
                        retry_count=retry_count,
                        input_char_count=len(system_prompt) + len(grounded_prompt),
                        output_char_count=len(output_text),
                        prompt_eval_count=prompt_eval_count,
                        eval_count=eval_count,
                    )
                )

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


def _ollama_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Inline references and retain Ollama's reliable structured-output subset."""

    definitions = schema.get("$defs", {})
    supported = {
        "type",
        "properties",
        "required",
        "items",
        "enum",
        "anyOf",
        "additionalProperties",
    }

    def simplify(value: object) -> object:
        if isinstance(value, list):
            return [simplify(item) for item in value]
        if not isinstance(value, dict):
            return value
        reference = value.get("$ref")
        if isinstance(reference, str) and reference.startswith("#/$defs/"):
            resolved = definitions.get(reference.removeprefix("#/$defs/"))
            if isinstance(resolved, dict):
                return simplify(resolved)
        result: dict[str, object] = {}
        for key, item in value.items():
            if key == "properties" and isinstance(item, dict):
                result[key] = {name: simplify(field) for name, field in item.items()}
            elif key in supported:
                result[key] = simplify(item)
        return result

    result = simplify(schema)
    return result if isinstance(result, dict) else {"type": "object"}


def _decode_json_output(value: str) -> object:
    """Recover one JSON value from common local-model formatting wrappers."""

    text = value.strip()
    if text.startswith("```"):
        first_newline = text.find("\n")
        if first_newline >= 0:
            text = text[first_newline + 1 :]
        if text.endswith("```"):
            text = text[:-3].rstrip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        starts = [index for index in (text.find("{"), text.find("[")) if index >= 0]
        if not starts:
            raise ValueError("model output did not contain a JSON value") from None
        try:
            decoded, _end = json.JSONDecoder().raw_decode(text[min(starts) :])
        except json.JSONDecodeError as error:
            raise ValueError("model output contained invalid JSON") from error
        return decoded


def _repair_body(body: dict[str, Any], invalid_output: str) -> dict[str, Any]:
    """Ask the same local model to repair one malformed structured response."""

    messages = list(body.get("messages") or [])
    messages.extend(
        [
            {"role": "assistant", "content": invalid_output[:12_000]},
            {
                "role": "user",
                "content": (
                    "The previous response was incomplete or invalid. Return one complete JSON "
                    "value matching the required schema, with no markdown or explanation."
                ),
            },
        ]
    )
    return {**body, "messages": messages}


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
