"""Runtime configuration and public-repository-safe storage resolution."""

from __future__ import annotations

from pathlib import Path

from platformdirs import user_data_path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Local runtime settings.

    No setting defaults to a path inside the source checkout. Environment variables may
    override these values with the ``NERVE_CENTER_`` prefix.
    """

    model_config = SettingsConfigDict(env_prefix="NERVE_CENTER_", extra="ignore")

    host: str = "127.0.0.1"
    port: int = Field(default=8765, ge=1, le=65535)
    scheduler_poll_seconds: float = Field(default=1.0, ge=0.1, le=60.0)
    module_heartbeat_timeout_seconds: float = Field(default=15.0, ge=5.0, le=300.0)
    data_dir: Path = Field(default_factory=lambda: user_data_path("Nerve Center", "TWS"))
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_timeout_seconds: float = Field(default=180.0, ge=1.0, le=3600.0)
    ollama_default_model: str | None = None
    ollama_allow_model_fallback: bool = True

    @property
    def manager_endpoint(self) -> str:
        host = "127.0.0.1" if self.host in {"0.0.0.0", "::"} else self.host
        return f"http://{host}:{self.port}"

    @property
    def database_path(self) -> Path:
        return self.data_dir / "nerve-center.sqlite3"

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.database_path.as_posix()}"

    @property
    def modules_data_dir(self) -> Path:
        return self.data_dir / "modules"

    def module_data_dir(self, storage_namespace: str) -> Path:
        if not storage_namespace or any(
            character not in "abcdefghijklmnopqrstuvwxyz0123456789_.-"
            for character in storage_namespace
        ):
            raise ValueError("invalid module storage namespace")
        return self.modules_data_dir / storage_namespace

    def ensure_runtime_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.modules_data_dir.mkdir(parents=True, exist_ok=True)
