"""Manager-owned Model Lab service with isolated local benchmark evidence."""

from __future__ import annotations

import hashlib
import json
import re
from contextlib import suppress
from dataclasses import asdict
from typing import Any

from jsonschema import SchemaError, ValidationError, validate

from nerve_center.persistence.model_lab import (
    BenchmarkCorpusItem,
    BenchmarkResultSnapshot,
    ModelLabRepository,
    ModelLabSessionSnapshot,
    ModelLabSettingsSnapshot,
)
from nerve_center.persistence.providers import ModelEvidenceRepository
from nerve_center.providers.base import ModelBlindRequest
from nerve_center.providers.errors import ProviderError
from nerve_center.providers.manager import ProviderManager
from nerve_center.scheduler.work_queue import WorkQueueService

_SECRET_KEY = re.compile(
    r"(api[_-]?key|token|password|credential|secret)", re.IGNORECASE
)
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(api[_-]?key|token|password|secret)\s*[:=]\s*([^\s,;]+)"
)
_BEARER = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+")


class ModelLabDisabledError(RuntimeError):
    pass


class ModelLabBusyError(RuntimeError):
    pass


class ModelLabService:
    def __init__(
        self,
        repository: ModelLabRepository,
        evidence: ModelEvidenceRepository,
        providers: ProviderManager | None,
        queue: WorkQueueService,
    ) -> None:
        self.repository = repository
        self.evidence = evidence
        self.providers = providers
        self.queue = queue

    def settings(self) -> ModelLabSettingsSnapshot:
        return self.repository.settings()

    def update_settings(
        self,
        *,
        enabled: bool,
        capture_enabled: bool,
        excluded_modules: list[str],
    ) -> ModelLabSettingsSnapshot:
        return self.repository.update_settings(
            enabled=enabled,
            capture_enabled=capture_enabled,
            excluded_modules=excluded_modules,
        )

    def harvest(self) -> int:
        settings = self.repository.settings()
        if not settings.enabled or not settings.capture_enabled:
            return 0
        created = 0
        excluded = set(settings.excluded_modules)
        for item in self.repository.completed_llm_work():
            if item.module_id in excluded:
                continue
            if item.requirements.get("model_lab_capture") is False:
                continue
            system_prompt = item.payload.get("system_prompt")
            user_prompt = item.payload.get("user_prompt")
            expected_output = item.result_payload.get("value")
            if (
                not isinstance(system_prompt, str)
                or not isinstance(user_prompt, str)
                or not item.output_contract
                or not isinstance(expected_output, (dict, list))
            ):
                continue
            safe_system = _redact_text(system_prompt)
            safe_user = _redact_text(user_prompt)
            # JSON schema is structural contract data, not a credential value. Preserve it
            # exactly so a property named "token" or "secret" does not break replay.
            safe_schema = dict(item.output_contract)
            safe_requirements = _safe_requirements(item.requirements)
            safe_output = _redact_value(expected_output)
            fingerprint = _fingerprint(
                item.module_id,
                item.task_id,
                str(item.requirements.get("contract_version") or item.task_id),
                safe_system,
                safe_user,
                safe_schema,
            )
            manager = item.result_payload.get("manager")
            manager_metadata = manager if isinstance(manager, dict) else {}
            _, was_created = self.repository.add_corpus(
                fingerprint=fingerprint,
                module_id=item.module_id,
                task_id=item.task_id,
                run_id=item.run_id,
                work_request_id=item.request_id,
                contract_version=str(
                    item.requirements.get("contract_version") or item.task_id
                ),
                system_prompt=safe_system,
                user_prompt=safe_user,
                output_schema=safe_schema,
                requirements=safe_requirements,
                expected_output=safe_output,
                production_provider=_optional_str(manager_metadata.get("provider")),
                production_model=_optional_str(manager_metadata.get("model")),
                production_call_id=_optional_str(
                    manager_metadata.get("provider_call_id")
                ),
                created_at=item.completed_at,
            )
            created += int(was_created)
        return created

    async def overview(self) -> dict[str, Any]:
        self.harvest()
        if self.providers is not None:
            with suppress(ProviderError):
                await self.providers.list_models()
        evidence = {
            task_id: [asdict(item) for item in self.evidence.task_evidence(task_id)]
            for task_id in self.repository.task_ids()
        }
        settings = self.repository.settings()
        active = self.repository.active_session()
        latest = active or self.repository.latest_session()
        corpus = self.repository.list_corpus(limit=50)
        results = self.repository.list_results(limit=50)
        return {
            "settings": _settings_dict(settings),
            "models": [asdict(item) for item in self.evidence.list_models()],
            "task_evidence": evidence,
            "corpus_count": self.repository.corpus_count(),
            "corpus": [_corpus_summary(item) for item in corpus],
            "exploration_session": asdict(latest) if latest is not None else None,
            "benchmark_results": [asdict(item) for item in results],
            "production_queue": asdict(self.queue.status()),
        }

    def start_exploration(
        self, *, duration_seconds: int, max_attempts: int
    ) -> ModelLabSessionSnapshot:
        self._require_enabled()
        return self.repository.start_session(duration_seconds, max_attempts)

    async def replay(
        self,
        corpus_id: str,
        *,
        provider: str,
        model: str,
    ) -> BenchmarkResultSnapshot:
        self._require_enabled()
        if self.providers is None:
            raise ModelLabDisabledError("No manager-owned JSON provider is available")
        queue = self.queue.status()
        if queue.queued > 0 or queue.claimed > 0:
            raise ModelLabBusyError(
                "Production LLM work is queued or running; Model Lab will not preempt it"
            )
        session = self.repository.active_session()
        if session is None:
            raise ValueError("No active Model Lab exploration session")
        corpus = self.repository.get_corpus(corpus_id)
        self.repository.consume_attempt(session.id)
        request = ModelBlindRequest(
            task_id=corpus.task_id,
            request_id=f"model-lab:{corpus.id}:{session.attempts_used + 1}",
            system_prompt=corpus.system_prompt,
            user_prompt=corpus.user_prompt,
            output_schema=corpus.output_schema,
            requirements={
                **corpus.requirements,
                "structured_output": True,
                "fallback_policy": "none",
                "model_lab_capture": False,
            },
            contract_version=corpus.contract_version,
        )
        try:
            generated = await self.providers.execute_specific(
                request,
                provider_name=provider,
                model_id=model,
            )
            schema_valid = True
            error_code = None
            try:
                validate(generated.value, corpus.output_schema)
            except (SchemaError, ValidationError):
                schema_valid = False
                error_code = "SCHEMA_VALIDATION_FAILED"
            return self.repository.record_result(
                corpus_id=corpus.id,
                session_id=session.id,
                provider=generated.metadata.provider,
                model=generated.metadata.model,
                status="succeeded" if schema_valid else "failed",
                schema_valid=schema_valid,
                duration_ms=generated.metadata.duration_ms,
                output=_redact_value(generated.value),
                error_code=error_code,
                provider_call_id=generated.metadata.id,
            )
        except ProviderError as error:
            return self.repository.record_result(
                corpus_id=corpus.id,
                session_id=session.id,
                provider=provider,
                model=model,
                status="failed",
                schema_valid=None,
                duration_ms=error.duration_ms or 0,
                output=None,
                error_code=error.code,
                provider_call_id=error.call_id,
            )

    def _require_enabled(self) -> None:
        if not self.repository.settings().enabled:
            raise ModelLabDisabledError("Model Lab is disabled")


def _fingerprint(
    module_id: str,
    task_id: str,
    contract_version: str,
    system_prompt: str,
    user_prompt: str,
    output_schema: dict[str, Any],
) -> str:
    canonical = json.dumps(
        {
            "module_id": module_id,
            "task_id": task_id,
            "contract_version": contract_version,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "output_schema": output_schema,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _safe_requirements(requirements: dict[str, Any]) -> dict[str, Any]:
    return {
        str(key): _redact_value(value)
        for key, value in requirements.items()
        if not _SECRET_KEY.search(str(key))
    }


def _redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): (
                "[REDACTED]"
                if _SECRET_KEY.search(str(key))
                else _redact_value(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, tuple):
        return [_redact_value(item) for item in value]
    if isinstance(value, str):
        return _redact_text(value)
    return value


def _redact_text(value: str) -> str:
    redacted = _SECRET_ASSIGNMENT.sub(
        lambda match: f"{match.group(1)}=[REDACTED]", value
    )
    return _BEARER.sub("Bearer [REDACTED]", redacted)


def _optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _settings_dict(settings: ModelLabSettingsSnapshot) -> dict[str, Any]:
    return {
        "enabled": settings.enabled,
        "capture_enabled": settings.capture_enabled,
        "excluded_modules": list(settings.excluded_modules),
        "updated_at": settings.updated_at,
    }


def _corpus_summary(item: BenchmarkCorpusItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "module_id": item.module_id,
        "task_id": item.task_id,
        "contract_version": item.contract_version,
        "production_provider": item.production_provider,
        "production_model": item.production_model,
        "created_at": item.created_at,
    }
