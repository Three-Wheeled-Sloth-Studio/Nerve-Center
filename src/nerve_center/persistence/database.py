"""SQLite initialization for local runtime state."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from importlib import import_module

from sqlalchemy import Connection, create_engine, event, text
from sqlalchemy.orm import Session

from nerve_center.config import Settings
from nerve_center.persistence.models import Base

SCHEMA_VERSION = 14


class Database:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.previous_schema_version: int | None = None
        self.engine = create_engine(settings.database_url, future=True)
        event.listen(self.engine, "connect", _configure_sqlite)

    def initialize(self) -> None:
        self.settings.ensure_runtime_directories()
        import_module("nerve_center.persistence.application_tables")
        import_module("nerve_center.persistence.attention")
        import_module("nerve_center.persistence.code_shop")
        import_module("nerve_center.persistence.model_lab")
        import_module("nerve_center.persistence.module_permissions")
        Base.metadata.create_all(self.engine)
        with self.engine.begin() as connection:
            self.previous_schema_version = _migrate(connection)

    @contextmanager
    def session(self) -> Iterator[Session]:
        with Session(self.engine) as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise


def _migrate(connection: Connection) -> int:
    connection.execute(
        text("CREATE TABLE IF NOT EXISTS schema_state (version INTEGER NOT NULL)")
    )
    existing = connection.execute(
        text("SELECT COUNT(*) FROM schema_state")
    ).scalar_one()
    if existing == 0:
        connection.execute(text("INSERT INTO schema_state (version) VALUES (1)"))
        previous_version = 1
    else:
        previous_version = int(
            connection.execute(text("SELECT version FROM schema_state LIMIT 1")).scalar_one()
        )

    tables = {
        row[0]
        for row in connection.execute(
            text("SELECT name FROM sqlite_master WHERE type = 'table'")
        ).fetchall()
    }
    if "runs" in tables:
        columns = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(runs)")).fetchall()
        }
        if "budget" not in columns:
            connection.execute(
                text("ALTER TABLE runs ADD COLUMN budget JSON NOT NULL DEFAULT '{}'")
            )
        if "budget_usage" not in columns:
            connection.execute(
                text(
                    "ALTER TABLE runs ADD COLUMN budget_usage JSON NOT NULL DEFAULT '{}'"
                )
            )
        if "session_id" not in columns:
            connection.execute(text("ALTER TABLE runs ADD COLUMN session_id VARCHAR(36)"))
        if "module_priority" not in columns:
            connection.execute(
                text("ALTER TABLE runs ADD COLUMN module_priority INTEGER NOT NULL DEFAULT 10")
            )
    connection.execute(
        text("UPDATE schema_state SET version = :version"),
        {"version": SCHEMA_VERSION},
    )
    return previous_version


def _configure_sqlite(dbapi_connection: object, _connection_record: object) -> None:
    cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()
