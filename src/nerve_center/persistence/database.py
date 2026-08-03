"""SQLite initialization for local runtime state."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Connection, create_engine, event, text
from sqlalchemy.orm import Session

from nerve_center.config import Settings
from nerve_center.persistence import application_tables as _application_tables
from nerve_center.persistence.models import Base

SCHEMA_VERSION = 6


class Database:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.engine = create_engine(settings.database_url, future=True)
        event.listen(self.engine, "connect", _configure_sqlite)

    def initialize(self) -> None:
        self.settings.ensure_runtime_directories()
        Base.metadata.create_all(self.engine)
        with self.engine.begin() as connection:
            _migrate(connection)

    @contextmanager
    def session(self) -> Iterator[Session]:
        with Session(self.engine) as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise


def _migrate(connection: Connection) -> None:
    connection.execute(
        text("CREATE TABLE IF NOT EXISTS schema_state (version INTEGER NOT NULL)")
    )
    existing = connection.execute(
        text("SELECT COUNT(*) FROM schema_state")
    ).scalar_one()
    if existing == 0:
        connection.execute(text("INSERT INTO schema_state (version) VALUES (1)"))

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
    connection.execute(
        text("UPDATE schema_state SET version = :version"),
        {"version": SCHEMA_VERSION},
    )


def _configure_sqlite(dbapi_connection: object, _connection_record: object) -> None:
    cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()
