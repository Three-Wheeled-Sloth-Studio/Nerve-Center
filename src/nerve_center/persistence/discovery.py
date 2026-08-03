"""Persistence repositories for companies, sources, scans, jobs, and search cache."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import or_, select

from nerve_center.discovery.models import (
    Company,
    DiscoverySource,
    JobProvenance,
    NormalizedJobOpening,
    ScanStatus,
    SourceHealth,
    SourceScanRecord,
)
from nerve_center.discovery.normalization import opening_fingerprint
from nerve_center.persistence.database import Database
from nerve_center.persistence.models import (
    CompanyModel,
    DiscoverySourceModel,
    JobOpeningModel,
    JobProvenanceModel,
    SearchCacheModel,
    SourceScanModel,
)


class CompanyRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def upsert(self, company: Company) -> Company:
        with self.database.session() as session:
            model = session.get(CompanyModel, company.id)
            if model is None:
                model = session.scalar(
                    select(CompanyModel).where(CompanyModel.domain == company.domain)
                )
            values = company.model_dump(mode="python")
            if model is None:
                session.add(CompanyModel(**values))
            else:
                for key, value in values.items():
                    setattr(model, key, value)
        return company

    def get(self, company_id: str) -> Company:
        with self.database.session() as session:
            model = session.get(CompanyModel, company_id)
            if model is None:
                raise KeyError(f"unknown company: {company_id}")
            return Company.model_validate(_company_values(model))

    def list(self) -> list[Company]:
        with self.database.session() as session:
            models = session.scalars(
                select(CompanyModel).order_by(CompanyModel.canonical_name)
            ).all()
            return [Company.model_validate(_company_values(item)) for item in models]


class DiscoverySourceRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def upsert(self, source: DiscoverySource) -> DiscoverySource:
        with self.database.session() as session:
            model = session.get(DiscoverySourceModel, source.id)
            values = source.model_dump(mode="python")
            if model is None:
                session.add(DiscoverySourceModel(**values))
            else:
                definition_fields = (
                    "company_id",
                    "name",
                    "kind",
                    "acquisition_class",
                    "base_url",
                    "configuration",
                    "parser_version",
                    "scan_interval_minutes",
                    "enabled",
                    "policy_notes",
                )
                for key in definition_fields:
                    setattr(model, key, values[key])
                model.updated_at = source.updated_at
                values = _source_values(model)
                source = DiscoverySource.model_validate(values)
        return source

    def get(self, source_id: str) -> DiscoverySource:
        with self.database.session() as session:
            model = session.get(DiscoverySourceModel, source_id)
            if model is None:
                raise KeyError(f"unknown discovery source: {source_id}")
            return DiscoverySource.model_validate(_source_values(model))

    def list(self, *, enabled_only: bool = False) -> list[DiscoverySource]:
        statement = select(DiscoverySourceModel).order_by(DiscoverySourceModel.name)
        if enabled_only:
            statement = statement.where(DiscoverySourceModel.enabled.is_(True))
        with self.database.session() as session:
            return [
                DiscoverySource.model_validate(_source_values(item))
                for item in session.scalars(statement).all()
            ]

    def list_due(self, now: datetime | None = None) -> list[DiscoverySource]:
        current = now or datetime.now(UTC)
        statement = (
            select(DiscoverySourceModel)
            .where(
                DiscoverySourceModel.enabled.is_(True),
                or_(
                    DiscoverySourceModel.next_scan_at.is_(None),
                    DiscoverySourceModel.next_scan_at <= current,
                ),
            )
            .order_by(DiscoverySourceModel.next_scan_at, DiscoverySourceModel.name)
        )
        with self.database.session() as session:
            return [
                DiscoverySource.model_validate(_source_values(item))
                for item in session.scalars(statement).all()
            ]

    def list_scans(
        self,
        source_id: str,
        *,
        limit: int = 100,
    ) -> list[SourceScanRecord]:
        if limit < 1:
            raise ValueError("limit must be at least 1")
        with self.database.session() as session:
            if session.get(DiscoverySourceModel, source_id) is None:
                raise KeyError(f"unknown discovery source: {source_id}")
            models = session.scalars(
                select(SourceScanModel)
                .where(SourceScanModel.source_id == source_id)
                .order_by(SourceScanModel.finished_at.desc())
                .limit(limit)
            ).all()
            return [
                SourceScanRecord.model_validate(
                    {
                        "id": item.id,
                        "source_id": item.source_id,
                        "started_at": _as_utc(item.started_at),
                        "finished_at": _as_utc(item.finished_at),
                        "status": item.status,
                        "requests_made": item.requests_made,
                        "openings_found": item.openings_found,
                        "http_status": item.http_status,
                        "safe_detail": item.safe_detail,
                    }
                )
                for item in models
            ]

    def record_scan(
        self,
        source_id: str,
        *,
        started_at: datetime,
        finished_at: datetime,
        status: ScanStatus,
        requests_made: int,
        openings_found: int,
        http_status: int | None = None,
        safe_detail: dict[str, object] | None = None,
    ) -> SourceScanRecord:
        scan = SourceScanRecord(
            id=str(uuid4()),
            source_id=source_id,
            started_at=started_at,
            finished_at=finished_at,
            status=status,
            requests_made=requests_made,
            openings_found=openings_found,
            http_status=http_status,
            safe_detail=safe_detail or {},
        )
        with self.database.session() as session:
            source = session.get(DiscoverySourceModel, source_id)
            if source is None:
                raise KeyError(f"unknown discovery source: {source_id}")
            session.add(SourceScanModel(**scan.model_dump(mode="python")))
            source.last_scan_at = finished_at
            source.updated_at = finished_at
            if status in {ScanStatus.SUCCEEDED, ScanStatus.PARTIAL}:
                source.health = (
                    SourceHealth.HEALTHY.value
                    if status is ScanStatus.SUCCEEDED
                    else SourceHealth.DEGRADED.value
                )
                source.last_success_at = finished_at
                source.consecutive_failures = 0
                multiplier = 1
            else:
                source.consecutive_failures += 1
                multiplier = min(2 ** min(source.consecutive_failures, 6), 64)
                if status is ScanStatus.CHALLENGED:
                    source.health = SourceHealth.CHALLENGED.value
                    source.challenge_count += 1
                elif status is ScanStatus.THROTTLED:
                    source.health = SourceHealth.DEGRADED.value
                    source.rate_limit_count += 1
                elif status is ScanStatus.ACCESS_FAILED and http_status in {401, 403}:
                    source.health = SourceHealth.BLOCKED.value
                else:
                    source.health = SourceHealth.DEGRADED.value
            source.next_scan_at = finished_at + timedelta(
                minutes=source.scan_interval_minutes * multiplier
            )
        return scan


class JobOpeningRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def upsert(self, opening: NormalizedJobOpening) -> NormalizedJobOpening:
        fingerprint = opening_fingerprint(
            opening.company_domain,
            opening.title,
            opening.location_text,
        )
        with self.database.session() as session:
            model = session.get(JobOpeningModel, opening.id)
            if model is None:
                model = session.scalar(
                    select(JobOpeningModel).where(
                        JobOpeningModel.company_id == opening.company_id,
                        or_(
                            JobOpeningModel.canonical_url == opening.canonical_url,
                            JobOpeningModel.fingerprint == fingerprint,
                        ),
                    )
                )
            if model is None:
                model = JobOpeningModel(
                    id=opening.id,
                    company_id=opening.company_id,
                    title=opening.title,
                    canonical_url=opening.canonical_url,
                    fingerprint=fingerprint,
                    external_id=opening.external_id,
                    active=opening.active,
                    first_discovered_at=opening.discovered_at,
                    last_discovered_at=opening.discovered_at,
                    payload=opening.model_dump(mode="json"),
                )
                session.add(model)
            else:
                existing = NormalizedJobOpening.model_validate(model.payload)
                merged = _merge_openings(existing, opening)
                model.title = merged.title
                model.canonical_url = merged.canonical_url
                model.external_id = merged.external_id
                model.active = merged.active
                model.last_discovered_at = max(existing.discovered_at, opening.discovered_at)
                model.payload = merged.model_dump(mode="json")
                opening = merged
            existing_provenance = {
                (item.source_id, item.connector, item.source_url, item.external_id)
                for item in session.scalars(
                    select(JobProvenanceModel).where(JobProvenanceModel.job_id == model.id)
                ).all()
            }
            for provenance in opening.provenance:
                key = (
                    provenance.source_id,
                    provenance.connector,
                    provenance.source_url,
                    provenance.external_id,
                )
                if key in existing_provenance:
                    continue
                session.add(
                    JobProvenanceModel(
                        job_id=model.id,
                        **provenance.model_dump(mode="python"),
                    )
                )
        return opening

    def list(self, *, active_only: bool = True) -> list[NormalizedJobOpening]:
        statement = select(JobOpeningModel).order_by(JobOpeningModel.last_discovered_at.desc())
        if active_only:
            statement = statement.where(JobOpeningModel.active.is_(True))
        with self.database.session() as session:
            return [
                NormalizedJobOpening.model_validate(item.payload)
                for item in session.scalars(statement).all()
            ]


class SearchCacheRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def get(
        self,
        provider: str,
        query: str,
        now: datetime | None = None,
    ) -> dict[str, object] | None:
        current = now or datetime.now(UTC)
        key = _cache_key(provider, query)
        with self.database.session() as session:
            model = session.get(SearchCacheModel, key)
            if model is None or _as_utc(model.expires_at) <= current:
                if model is not None:
                    session.delete(model)
                return None
            return dict(model.payload)

    def put(
        self,
        provider: str,
        query: str,
        payload: dict[str, object],
        *,
        ttl: timedelta = timedelta(days=7),
        now: datetime | None = None,
    ) -> None:
        current = now or datetime.now(UTC)
        key = _cache_key(provider, query)
        with self.database.session() as session:
            model = session.get(SearchCacheModel, key)
            values = {
                "provider": provider,
                "query": query,
                "created_at": current,
                "expires_at": current + ttl,
                "payload": payload,
            }
            if model is None:
                session.add(SearchCacheModel(key=key, **values))
            else:
                for field, value in values.items():
                    setattr(model, field, value)


def _company_values(model: CompanyModel) -> dict[str, object]:
    values = {column.name: getattr(model, column.name) for column in CompanyModel.__table__.columns}
    values["created_at"] = _as_utc(values["created_at"])
    values["updated_at"] = _as_utc(values["updated_at"])
    return values


def _source_values(model: DiscoverySourceModel) -> dict[str, object]:
    values = {
        column.name: getattr(model, column.name)
        for column in DiscoverySourceModel.__table__.columns
    }
    for field in (
        "last_success_at",
        "last_scan_at",
        "next_scan_at",
        "created_at",
        "updated_at",
    ):
        if values[field] is not None:
            values[field] = _as_utc(values[field])
    return values


def _merge_openings(
    existing: NormalizedJobOpening,
    incoming: NormalizedJobOpening,
) -> NormalizedJobOpening:
    existing_direct = any(item.direct_employer_source for item in existing.provenance)
    incoming_direct = any(item.direct_employer_source for item in incoming.provenance)
    primary = incoming if incoming_direct and not existing_direct else existing
    secondary = existing if primary is incoming else incoming
    provenance_by_key = {
        (item.source_id, item.connector, item.source_url, item.external_id): item
        for item in [*existing.provenance, *incoming.provenance]
    }
    return primary.model_copy(
        update={
            "id": existing.id,
            "description": primary.description or secondary.description,
            "locations": list(dict.fromkeys([*primary.locations, *secondary.locations])),
            "location_text": primary.location_text or secondary.location_text,
            "employment_type": primary.employment_type or secondary.employment_type,
            "department": primary.department or secondary.department,
            "team": primary.team or secondary.team,
            "apply_url": primary.apply_url or secondary.apply_url,
            "posted_at": primary.posted_at or secondary.posted_at,
            "updated_at": primary.updated_at or secondary.updated_at,
            "valid_through": primary.valid_through or secondary.valid_through,
            "discovered_at": max(existing.discovered_at, incoming.discovered_at),
            "parser_confidence": max(existing.parser_confidence, incoming.parser_confidence),
            "active": existing.active or incoming.active,
            "provenance": list(provenance_by_key.values()),
        }
    )


def _cache_key(provider: str, query: str) -> str:
    normalized = f"{provider.strip().casefold()}|{' '.join(query.split()).casefold()}"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)
