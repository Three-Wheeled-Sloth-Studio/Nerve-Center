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
    data_dir: Path = Field(default_factory=lambda: user_data_path("Nerve Center", "TWS"))

    @property
    def database_path(self) -> Path:
        return self.data_dir / "nerve-center.sqlite3"

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.database_path.as_posix()}"

    def ensure_runtime_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
