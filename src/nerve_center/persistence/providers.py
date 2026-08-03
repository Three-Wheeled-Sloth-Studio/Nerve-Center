"""Secret-safe provider call metadata persistence."""

from __future__ import annotations

from nerve_center.persistence.database import Database
from nerve_center.persistence.models import ProviderCallModel
from nerve_center.providers.base import ProviderCallMetadata


class ProviderCallRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def record(self, metadata: ProviderCallMetadata) -> None:
        with self.database.session() as session:
            session.add(
                ProviderCallModel(
                    id=metadata.id,
                    provider=metadata.provider,
                    model=metadata.model,
                    contract_version=metadata.contract_version,
                    response_schema=metadata.response_schema,
                    started_at=metadata.started_at,
                    duration_ms=metadata.duration_ms,
                    status=metadata.status,
                    error_code=metadata.error_code,
                    retry_count=metadata.retry_count,
                    input_char_count=metadata.input_char_count,
                    output_char_count=metadata.output_char_count,
                    prompt_eval_count=metadata.prompt_eval_count,
                    eval_count=metadata.eval_count,
                )
            )
