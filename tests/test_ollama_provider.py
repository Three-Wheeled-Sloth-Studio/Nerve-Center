import asyncio
import json

import httpx
import pytest
from pydantic import BaseModel

from nerve_center.providers.base import ProviderCallMetadata
from nerve_center.providers.errors import ProviderError
from nerve_center.providers.ollama import OllamaProvider, _ollama_schema


class ExampleResponse(BaseModel):
    name: str
    score: int


class CaptureTelemetry:
    def __init__(self) -> None:
        self.items: list[ProviderCallMetadata] = []

    def record(self, metadata: ProviderCallMetadata) -> None:
        self.items.append(metadata)


def test_ollama_schema_retains_supported_bounds_and_drops_max_length() -> None:
    schema = _ollama_schema(
        {
            "type": "object",
            "properties": {
                "score": {"type": "number", "minimum": 0, "maximum": 1},
                "items": {"type": "array", "minItems": 1, "maxItems": 8},
                "label": {"type": "string", "minLength": 1, "maxLength": 100},
            },
        }
    )

    assert schema["properties"]["score"] == {
        "type": "number",
        "minimum": 0,
        "maximum": 1,
    }
    assert schema["properties"]["items"]["maxItems"] == 8
    assert schema["properties"]["label"] == {"type": "string", "minLength": 1}


def test_lists_models_and_parses_details() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/tags"
        return httpx.Response(
            200,
            json={
                "models": [
                    {
                        "name": "qwen3:8b",
                        "model": "qwen3:8b",
                        "modified_at": "2026-01-01T00:00:00Z",
                        "details": {
                            "family": "qwen3",
                            "parameter_size": "8B",
                            "quantization_level": "Q4_K_M",
                        },
                    }
                ]
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OllamaProvider(client=client)
    models = asyncio.run(provider.list_models())
    asyncio.run(client.aclose())

    assert models[0].id == "qwen3:8b"
    assert models[0].family == "qwen3"


def test_generates_schema_constrained_response_and_records_safe_metadata() -> None:
    telemetry = CaptureTelemetry()

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert request.url.path == "/api/chat"
        assert payload["stream"] is False
        assert payload["format"]["type"] == "object"
        assert set(payload["format"]["properties"]) == {"name", "score"}
        assert payload["options"]["temperature"] == 0
        return httpx.Response(
            200,
            json={
                "message": {"role": "assistant", "content": '{"name":"fit","score":91}'},
                "prompt_eval_count": 120,
                "eval_count": 18,
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OllamaProvider(client=client, telemetry=telemetry)
    result = asyncio.run(
        provider.generate_structured(
            model="qwen3:8b",
            system_prompt="system secret",
            user_prompt="user secret",
            response_type=ExampleResponse,
            contract_version="example-v1",
        )
    )
    asyncio.run(client.aclose())

    assert result.value.score == 91
    assert telemetry.items[0].status == "succeeded"
    assert telemetry.items[0].prompt_eval_count == 120
    assert "secret" not in telemetry.items[0].model_dump_json()


def test_records_retry_count_when_ollama_stays_unavailable() -> None:
    telemetry = CaptureTelemetry()

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OllamaProvider(client=client, telemetry=telemetry, max_retries=1)
    try:
        asyncio.run(
            provider.generate_structured(
                model="qwen3:8b",
                system_prompt="system",
                user_prompt="user",
                response_type=ExampleResponse,
                contract_version="example-v1",
            )
        )
    except ProviderError as error:
        assert error.code == "OLLAMA_UNREACHABLE"
    else:
        raise AssertionError("expected the unavailable provider to fail")
    finally:
        asyncio.run(client.aclose())

    assert telemetry.items[0].status == "failed"
    assert telemetry.items[0].retry_count == 1


def test_generates_model_blind_json_contract() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["model"] == "qwen3:8b"
        assert payload["format"]["required"] == ["score"]
        assert payload["format"]["properties"]["score"] == {
            "type": "integer",
            "minimum": 0,
            "maximum": 100,
        }
        return httpx.Response(
            200,
            json={"message": {"content": '{"score":88}'}, "eval_count": 5},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OllamaProvider(client=client)
    result = asyncio.run(
        provider.generate_json(
            model="qwen3:8b",
            system_prompt="system",
            user_prompt="user",
            output_schema={
                "type": "object",
                "properties": {
                    "score": {"type": "integer", "minimum": 0, "maximum": 100}
                },
                "required": ["score"],
            },
            contract_version="example-v1",
        )
    )
    asyncio.run(client.aclose())

    assert result.value == {"score": 88}
    assert result.metadata.model == "qwen3:8b"


def test_model_blind_json_recovers_fenced_structured_output() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"message": {"content": "```json\n{\"score\":88}\n```"}},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OllamaProvider(client=client)
    result = asyncio.run(
        provider.generate_json(
            model="gemma3:4b",
            system_prompt="system",
            user_prompt="user",
            output_schema={
                "type": "object",
                "properties": {"score": {"type": "integer"}},
                "required": ["score"],
            },
            contract_version="example-v1",
        )
    )
    asyncio.run(client.aclose())

    assert result.value == {"score": 88}
    assert result.metadata.model == "gemma3:4b"


def test_model_blind_json_retries_one_invalid_structured_response() -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        payload = json.loads(_request.content)
        assert len(payload["messages"]) == (2 if calls == 1 else 4)
        content = "{" if calls == 1 else '{"score":88}'
        return httpx.Response(200, json={"message": {"content": content}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OllamaProvider(client=client, max_retries=1)
    result = asyncio.run(
        provider.generate_json(
            model="gemma3:4b",
            system_prompt="system",
            user_prompt="user",
            output_schema={
                "type": "object",
                "properties": {"score": {"type": "integer"}},
                "required": ["score"],
            },
            contract_version="example-v1",
        )
    )
    asyncio.run(client.aclose())

    assert calls == 2
    assert result.value == {"score": 88}
    assert result.metadata.retry_count == 1


@pytest.mark.parametrize(
    ("invalid", "validator"),
    [
        ('{"label":"missing score"}', "required"),
        ('{"score":"high"}', "type"),
        ('{"score":50,"status":"maybe"}', "enum"),
    ],
)
def test_model_blind_json_repairs_schema_invalid_objects(
    invalid: str,
    validator: str,
) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        payload = json.loads(request.content)
        if calls == 2:
            repair_prompt = payload["messages"][-1]["content"]
            assert f"validator '{validator}'" in repair_prompt
            assert invalid not in repair_prompt
        content = invalid if calls == 1 else '{"score":88,"status":"accepted"}'
        return httpx.Response(200, json={"message": {"content": content}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OllamaProvider(client=client, max_retries=1)
    result = asyncio.run(
        provider.generate_json(
            model="qwen2.5:7b-instruct",
            system_prompt="system",
            user_prompt="user",
            output_schema={
                "type": "object",
                "properties": {
                    "score": {"type": "integer"},
                    "status": {"type": "string", "enum": ["accepted", "rejected"]},
                },
                "required": ["score", "status"],
                "additionalProperties": False,
            },
            contract_version="example-v1",
        )
    )
    asyncio.run(client.aclose())

    assert calls == 2
    assert result.value == {"score": 88, "status": "accepted"}
    assert result.metadata.retry_count == 1


def test_model_blind_json_reports_exhausted_schema_repair() -> None:
    telemetry = CaptureTelemetry()

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": {"content": '{"score":"bad"}'}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OllamaProvider(client=client, telemetry=telemetry, max_retries=1)
    with pytest.raises(ProviderError) as caught:
        asyncio.run(
            provider.generate_json(
                model="qwen2.5:7b-instruct",
                system_prompt="system",
                user_prompt="user",
                output_schema={
                    "type": "object",
                    "properties": {"score": {"type": "integer"}},
                    "required": ["score"],
                },
                contract_version="example-v1",
            )
        )
    asyncio.run(client.aclose())

    assert caught.value.code == "SCHEMA_VALIDATION_FAILED"
    assert caught.value.retry_count == 1
    assert telemetry.items[0].error_code == "SCHEMA_VALIDATION_FAILED"
    assert telemetry.items[0].retry_count == 1


def test_model_blind_json_rejects_scalar_then_repairs() -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        content = '42' if calls == 1 else '{"score":42}'
        return httpx.Response(200, json={"message": {"content": content}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OllamaProvider(client=client, max_retries=1)
    result = asyncio.run(
        provider.generate_json(
            model="gemma3:4b",
            system_prompt="system",
            user_prompt="user",
            output_schema={
                "type": "object",
                "properties": {
                    "score": {"type": "integer", "minimum": 0, "maximum": 100}
                },
                "required": ["score"],
            },
            contract_version="example-v1",
        )
    )
    asyncio.run(client.aclose())

    assert calls == 2
    assert result.value == {"score": 42}
