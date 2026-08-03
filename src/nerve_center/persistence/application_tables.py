"""SQLAlchemy tables for application tracking."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from nerve_center.persistence.models import Base


class ApplicationRecordModel(Base):
    __tablename__ = "application_records"

    job_id: Mapped[str] = mapped_column(
        ForeignKey("job_openings.id"),
        primary_key=True,
    )
    status: Mapped[str] = mapped_column(String(50), index=True)
    application_date: Mapped[date | None] = mapped_column(Date)
    source: Mapped[str | None] = mapped_column(Text)
    resume_variant_reference: Mapped[str | None] = mapped_column(Text)
    referral_status: Mapped[str] = mapped_column(String(50), index=True)
    response_date: Mapped[date | None] = mapped_column(Date)
    disposition_reason: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ApplicationEventModel(Base):
    __tablename__ = "application_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str] = mapped_column(
        ForeignKey("job_openings.id"),
        index=True,
    )
    from_status: Mapped[str | None] = mapped_column(String(50))
    to_status: Mapped[str] = mapped_column(String(50), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
