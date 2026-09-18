"""Durable manager-owned reusable resource profiles."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, DateTime, String, select
from sqlalchemy.orm import Mapped, mapped_column

from nerve_center.persistence.database import Database
from nerve_center.persistence.models import Base
from nerve_center.resource_profiles.domain import (
    MANAGER_DEFAULT_PROFILE_ID,
    ResourceProfile,
    manager_default_limits,
    normalize_limits,
)


class ResourceProfileModel(Base):
    __tablename__ = "core_resource_profiles"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(120))
    limits: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ResourceProfileStateModel(Base):
    __tablename__ = "core_resource_profile_state"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    selected_profile_id: Mapped[str] = mapped_column(String(100), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ResourceProfileNotFoundError(KeyError):
    pass


class ResourceProfileRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def initialize(self) -> None:
        now = datetime.now(UTC)
        with self.database.session() as session:
            default = session.get(ResourceProfileModel, MANAGER_DEFAULT_PROFILE_ID)
            if default is None:
                session.add(
                    ResourceProfileModel(
                        id=MANAGER_DEFAULT_PROFILE_ID,
                        display_name="Manager Default",
                        limits=manager_default_limits(),
                        created_at=now,
                        updated_at=now,
                    )
                )
            state = session.get(ResourceProfileStateModel, "global")
            if state is None:
                session.add(
                    ResourceProfileStateModel(
                        id="global",
                        selected_profile_id=MANAGER_DEFAULT_PROFILE_ID,
                        updated_at=now,
                    )
                )

    def list(self) -> list[ResourceProfile]:
        with self.database.session() as session:
            models = session.scalars(
                select(ResourceProfileModel).order_by(
                    ResourceProfileModel.display_name, ResourceProfileModel.id
                )
            ).all()
            return [_snapshot(item) for item in models]

    def get(self, profile_id: str) -> ResourceProfile:
        with self.database.session() as session:
            model = session.get(ResourceProfileModel, profile_id)
            if model is None:
                raise ResourceProfileNotFoundError(
                    f"resource profile {profile_id!r} was not found"
                )
            return _snapshot(model)

    def create(
        self,
        display_name: str,
        limits: dict[str, int | float],
    ) -> ResourceProfile:
        name = display_name.strip()
        if not name:
            raise ValueError("resource profile display_name is required")
        normalized = normalize_limits(limits)
        now = datetime.now(UTC)
        model = ResourceProfileModel(
            id=str(uuid4()),
            display_name=name,
            limits=normalized,
            created_at=now,
            updated_at=now,
        )
        with self.database.session() as session:
            session.add(model)
            session.flush()
            return _snapshot(model)

    def update(
        self,
        profile_id: str,
        *,
        display_name: str | None = None,
        limits: dict[str, int | float] | None = None,
    ) -> ResourceProfile:
        now = datetime.now(UTC)
        with self.database.session() as session:
            model = session.get(ResourceProfileModel, profile_id)
            if model is None:
                raise ResourceProfileNotFoundError(
                    f"resource profile {profile_id!r} was not found"
                )
            if display_name is not None:
                name = display_name.strip()
                if not name:
                    raise ValueError("resource profile display_name is required")
                model.display_name = name
            if limits is not None:
                model.limits = normalize_limits(limits)
            model.updated_at = now
            session.flush()
            return _snapshot(model)

    def select(self, profile_id: str) -> ResourceProfile:
        selected = self.get(profile_id)
        now = datetime.now(UTC)
        with self.database.session() as session:
            state = session.get(ResourceProfileStateModel, "global")
            if state is None:
                state = ResourceProfileStateModel(
                    id="global",
                    selected_profile_id=profile_id,
                    updated_at=now,
                )
                session.add(state)
            else:
                state.selected_profile_id = profile_id
                state.updated_at = now
            session.flush()
        return selected

    def selected_id(self) -> str:
        with self.database.session() as session:
            state = session.get(ResourceProfileStateModel, "global")
            if state is None:
                raise RuntimeError("resource profile repository was not initialized")
            return state.selected_profile_id


def _snapshot(model: ResourceProfileModel) -> ResourceProfile:
    return ResourceProfile(
        id=model.id,
        display_name=model.display_name,
        limits=normalize_limits(dict(model.limits or {})),
        created_at=_utc(model.created_at),
        updated_at=_utc(model.updated_at),
    )


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
