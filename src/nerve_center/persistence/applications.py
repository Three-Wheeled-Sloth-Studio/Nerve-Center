"""Persistence for application status and outcome history."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import literal_column, select

from nerve_center.applications.models import (
    RESPONSE_STATUSES,
    ApplicationEvent,
    ApplicationRecord,
    ApplicationStatus,
    ApplicationUpdate,
    ReferralStatus,
)
from nerve_center.persistence.application_tables import (
    ApplicationEventModel,
    ApplicationRecordModel,
)
from nerve_center.persistence.database import Database


class ApplicationRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def get(self, job_id: str) -> ApplicationRecord:
        with self.database.session() as session:
            model = session.get(ApplicationRecordModel, job_id)
            if model is None:
                raise KeyError(f"no application record for job: {job_id}")
            return _record(model)

    def get_or_default(self, job_id: str) -> ApplicationRecord:
        try:
            return self.get(job_id)
        except KeyError:
            return ApplicationRecord(job_id=job_id)

    def list(self) -> list[ApplicationRecord]:
        with self.database.session() as session:
            models = session.scalars(
                select(ApplicationRecordModel).order_by(
                    ApplicationRecordModel.updated_at.desc()
                )
            ).all()
            return [_record(item) for item in models]

    def save(
        self,
        job_id: str,
        update: ApplicationUpdate,
        *,
        now: datetime | None = None,
    ) -> ApplicationRecord:
        current_time = now or datetime.now(UTC)
        payload = update.model_dump(exclude_unset=True)
        with self.database.session() as session:
            model = session.get(ApplicationRecordModel, job_id)
            previous = (
                _record(model)
                if model is not None
                else ApplicationRecord(job_id=job_id)
            )
            values = previous.model_dump(mode="python")
            values.update(payload)
            next_status = ApplicationStatus(values["status"])
            if (
                next_status is ApplicationStatus.APPLIED
                and values["application_date"] is None
            ):
                values["application_date"] = current_time.date()
            if next_status in RESPONSE_STATUSES and values["response_date"] is None:
                values["response_date"] = current_time.date()
            values["referral_status"] = ReferralStatus(values["referral_status"])
            values["updated_at"] = current_time
            if model is None:
                values["created_at"] = current_time
            saved = ApplicationRecord.model_validate(values)
            changed_fields = _changed_fields(previous, saved)
            if model is None:
                session.add(
                    ApplicationRecordModel(**saved.model_dump(mode="python"))
                )
            elif changed_fields:
                for field, value in saved.model_dump(mode="python").items():
                    setattr(model, field, value)
            if model is None or previous.status is not saved.status:
                session.add(
                    ApplicationEventModel(
                        id=str(uuid4()),
                        job_id=job_id,
                        from_status=None if model is None else previous.status.value,
                        to_status=saved.status.value,
                        created_at=current_time,
                        detail={"changed_fields": changed_fields},
                    )
                )
            return saved

    def history(self, job_id: str) -> list[ApplicationEvent]:
        with self.database.session() as session:
            models = session.scalars(
                select(ApplicationEventModel)
                .where(ApplicationEventModel.job_id == job_id)
                .order_by(
                    ApplicationEventModel.created_at.desc(),
                    literal_column("rowid").desc(),
                )
            ).all()
            return [
                ApplicationEvent.model_validate(
                    {
                        "id": item.id,
                        "job_id": item.job_id,
                        "from_status": item.from_status,
                        "to_status": item.to_status,
                        "created_at": _as_utc(item.created_at),
                        "detail": item.detail,
                    }
                )
                for item in models
            ]


def _record(model: ApplicationRecordModel) -> ApplicationRecord:
    return ApplicationRecord.model_validate(
        {
            "job_id": model.job_id,
            "status": model.status,
            "application_date": model.application_date,
            "source": model.source,
            "resume_variant_reference": model.resume_variant_reference,
            "referral_status": model.referral_status,
            "response_date": model.response_date,
            "disposition_reason": model.disposition_reason,
            "notes": model.notes,
            "created_at": _as_utc(model.created_at),
            "updated_at": _as_utc(model.updated_at),
        }
    )


def _changed_fields(
    previous: ApplicationRecord,
    saved: ApplicationRecord,
) -> list[str]:
    ignored = {"updated_at"}
    before = previous.model_dump(mode="json")
    after = saved.model_dump(mode="json")
    return [
        field
        for field, value in after.items()
        if field not in ignored and before.get(field) != value
    ]


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)
