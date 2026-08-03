"""SQLite initialization for local runtime state."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session

from nerve_center.config import Settings
from nerve_center.persistence.models import Base


class Database:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.engine = create_engine(settings.database_url, future=True)
        event.listen(self.engine, "connect", _configure_sqlite)

    def initialize(self) -> None:
        self.settings.ensure_runtime_directories()
        Base.metadata.create_all(self.engine)
        with self.engine.begin() as connection:
            connection.execute(text("CREATE TABLE IF NOT EXISTS schema_state (version INTEGER NOT NULL)"))
            existing = connection.execute(text("SELECT COUNT(*) FROM schema_state")).scalar_one()
            if existing == 0:
                connection.execute(text("INSERT INTO schema_state (version) VALUES (1)"))

    @contextmanager
    def session(self) -> Iterator[Session]:
        with Session(self.engine) as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise


def _configure_sqlite(dbapi_connection: object, _connection_record: object) -> None:
    cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()
