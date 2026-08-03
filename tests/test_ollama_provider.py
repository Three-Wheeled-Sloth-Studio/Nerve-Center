import asyncio
import json

import httpx
from pydantic import BaseModel

from nerve_center.providers.base import ProviderCallMetadata
from nerve_center.providers.errors import ProviderError
from nerve_center.providers.ollama import OllamaProvider


class ExampleResponse(BaseModel):
    name: str
    score: int


class CaptureTelemetry:
    def __init__(self) -> None:
        self.items: list[ProviderCallMetadata] = []

    def record(self, metadata: ProviderCallMetadata) -> None:
        self.items.append(metadata)


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
