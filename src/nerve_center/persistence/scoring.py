"""Persistence for location preferences, enrichment, rules, fit, and score history."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from nerve_center.persistence.database import Database
from nerve_center.persistence.models import (
    CompanyEnrichmentModel,
    FitAnalysisModel,
    JobEnrichmentModel,
    LocationPreferencesModel,
    OpportunityScoreModel,
    ScoringRuleModel,
    ScoringSettingsModel,
)
from nerve_center.scoring.models import (
    CompanyEnrichment,
    JobEnrichment,
    JobFitAnalysis,
    LocationPreferences,
    OpportunityScore,
    ScoringRule,
    ScoringSettings,
)


class LocationPreferencesRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def get(self) -> LocationPreferences:
        with self.database.session() as session:
            model = session.get(LocationPreferencesModel, "canonical")
            return (
                LocationPreferences()
                if model is None
                else LocationPreferences.model_validate(model.payload)
            )

    def save(self, preferences: LocationPreferences) -> LocationPreferences:
        with self.database.session() as session:
            model = session.get(LocationPreferencesModel, preferences.id)
            existing_version = model.version if model else preferences.version
            saved = preferences.model_copy(
                update={
                    "version": existing_version + 1,
                    "updated_at": datetime.now(UTC),
                }
            )
            if model is None:
                session.add(
                    LocationPreferencesModel(
                        id=saved.id,
                        version=saved.version,
                        updated_at=saved.updated_at,
                        payload=saved.model_dump(mode="json"),
                    )
                )
            else:
                model.version = saved.version
                model.updated_at = saved.updated_at
                model.payload = saved.model_dump(mode="json")
        return saved


class CompanyEnrichmentRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def get(self, company_id: str) -> CompanyEnrichment:
        with self.database.session() as session:
            model = session.get(CompanyEnrichmentModel, company_id)
            return (
                CompanyEnrichment(company_id=company_id)
                if model is None
                else CompanyEnrichment.model_validate(model.payload)
            )

    def save(self, enrichment: CompanyEnrichment) -> CompanyEnrichment:
        saved = enrichment.model_copy(update={"updated_at": datetime.now(UTC)})
        with self.database.session() as session:
            model = session.get(CompanyEnrichmentModel, saved.company_id)
            if model is None:
                session.add(
                    CompanyEnrichmentModel(
                        company_id=saved.company_id,
                        updated_at=saved.updated_at,
                        payload=saved.model_dump(mode="json"),
                    )
                )
            else:
                model.updated_at = saved.updated_at
                model.payload = saved.model_dump(mode="json")
        return saved


class JobEnrichmentRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def get(self, job_id: str) -> JobEnrichment:
        with self.database.session() as session:
            model = session.get(JobEnrichmentModel, job_id)
            return (
                JobEnrichment(job_id=job_id)
                if model is None
                else JobEnrichment.model_validate(model.payload)
            )

    def save(self, enrichment: JobEnrichment) -> JobEnrichment:
        saved = enrichment.model_copy(update={"updated_at": datetime.now(UTC)})
        with self.database.session() as session:
            model = session.get(JobEnrichmentModel, saved.job_id)
            if model is None:
                session.add(
                    JobEnrichmentModel(
                        job_id=saved.job_id,
                        updated_at=saved.updated_at,
                        payload=saved.model_dump(mode="json"),
                    )
                )
            else:
                model.updated_at = saved.updated_at
                model.payload = saved.model_dump(mode="json")
        return saved


class FitAnalysisRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def save(self, analysis: JobFitAnalysis) -> JobFitAnalysis:
        with self.database.session() as session:
            if session.get(FitAnalysisModel, analysis.id) is None:
                session.add(
                    FitAnalysisModel(
                        id=analysis.id,
                        job_id=analysis.job_id,
                        profile_version=analysis.profile_version,
                        contract_version=analysis.contract_version,
                        model=analysis.model,
                        created_at=analysis.created_at,
                        payload=analysis.model_dump(mode="json"),
                    )
                )
        return analysis

    def get(self, analysis_id: str) -> JobFitAnalysis:
        with self.database.session() as session:
            model = session.get(FitAnalysisModel, analysis_id)
            if model is None:
                raise KeyError(f"unknown fit analysis: {analysis_id}")
            return JobFitAnalysis.model_validate(model.payload)

    def latest(self, job_id: str) -> JobFitAnalysis:
        with self.database.session() as session:
            model = session.scalar(
                select(FitAnalysisModel)
                .where(FitAnalysisModel.job_id == job_id)
                .order_by(FitAnalysisModel.created_at.desc())
            )
            if model is None:
                raise KeyError(f"no fit analysis for job: {job_id}")
            return JobFitAnalysis.model_validate(model.payload)

    def list(self, job_id: str) -> list[JobFitAnalysis]:
        with self.database.session() as session:
            return [
                JobFitAnalysis.model_validate(item.payload)
                for item in session.scalars(
                    select(FitAnalysisModel)
                    .where(FitAnalysisModel.job_id == job_id)
                    .order_by(FitAnalysisModel.created_at.desc())
                ).all()
            ]


class ScoringSettingsRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def get(self) -> ScoringSettings:
        with self.database.session() as session:
            model = session.get(ScoringSettingsModel, "canonical")
            return (
                ScoringSettings()
                if model is None
                else ScoringSettings.model_validate(model.payload)
            )

    def save(self, settings: ScoringSettings) -> ScoringSettings:
        with self.database.session() as session:
            model = session.get(ScoringSettingsModel, settings.id)
            existing_version = model.version if model else settings.version
            saved = settings.model_copy(
                update={
                    "version": existing_version + 1,
                    "updated_at": datetime.now(UTC),
                }
            )
            if model is None:
                session.add(
                    ScoringSettingsModel(
                        id=saved.id,
                        version=saved.version,
                        contract_version=saved.contract_version,
                        updated_at=saved.updated_at,
                        payload=saved.model_dump(mode="json"),
                    )
                )
            else:
                model.version = saved.version
                model.contract_version = saved.contract_version
                model.updated_at = saved.updated_at
                model.payload = saved.model_dump(mode="json")
        return saved


class ScoringRuleRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def upsert(self, rule: ScoringRule) -> ScoringRule:
        saved = rule.model_copy(update={"updated_at": datetime.now(UTC)})
        with self.database.session() as session:
            model = session.get(ScoringRuleModel, saved.id)
            values = {
                "target": saved.target.value,
                "action": saved.action.value,
                "pattern": saved.pattern,
                "enabled": saved.enabled,
                "updated_at": saved.updated_at,
                "payload": saved.model_dump(mode="json"),
            }
            if model is None:
                session.add(ScoringRuleModel(id=saved.id, **values))
            else:
                for field, value in values.items():
                    setattr(model, field, value)
        return saved

    def list(self, *, enabled_only: bool = False) -> list[ScoringRule]:
        statement = select(ScoringRuleModel).order_by(ScoringRuleModel.updated_at.desc())
        if enabled_only:
            statement = statement.where(ScoringRuleModel.enabled.is_(True))
        with self.database.session() as session:
            return [
                ScoringRule.model_validate(item.payload)
                for item in session.scalars(statement).all()
            ]

    def delete(self, rule_id: str) -> None:
        with self.database.session() as session:
            model = session.get(ScoringRuleModel, rule_id)
            if model is None:
                raise KeyError(f"unknown scoring rule: {rule_id}")
            session.delete(model)


class OpportunityScoreRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def append(self, score: OpportunityScore) -> OpportunityScore:
        with self.database.session() as session:
            session.add(
                OpportunityScoreModel(
                    id=score.id,
                    job_id=score.job_id,
                    profile_version=score.profile_version,
                    contract_version=score.contract_version,
                    settings_version=score.settings_version,
                    created_at=score.created_at,
                    priority=score.priority,
                    excluded=score.excluded,
                    retained=score.retained,
                    calibration_key=score.calibration_key,
                    payload=score.model_dump(mode="json"),
                )
            )
        return score

    def list(self, job_id: str) -> list[OpportunityScore]:
        with self.database.session() as session:
            return [
                OpportunityScore.model_validate(item.payload)
                for item in session.scalars(
                    select(OpportunityScoreModel)
                    .where(OpportunityScoreModel.job_id == job_id)
                    .order_by(
              OpportunityScoreModel.created_at.desc(),
              OpportunityScoreModel.id.desc(),
          )
                ).all()
            ]
