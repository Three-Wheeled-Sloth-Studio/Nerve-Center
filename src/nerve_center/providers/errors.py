"""Provider-neutral, secret-safe error contracts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ProviderError(RuntimeError):
    provider: str
    code: str
    safe_message: str
    retryable: bool = False
    status_code: int | None = None
    call_id: str | None = None
    model: str | None = None
    duration_ms: int = 0
    retry_count: int = 0

    def __post_init__(self) -> None:
        RuntimeError.__init__(self, self.safe_message)

    def as_dict(self) -> dict[str, str | int | bool | None]:
        return {
            "provider": self.provider,
            "code": self.code,
            "message": self.safe_message,
            "retryable": self.retryable,
            "status_code": self.status_code,
        }
