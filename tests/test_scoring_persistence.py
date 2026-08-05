from pathlib import Path

from nerve_center.config import Settings
from nerve_center.discovery.models import (
    AcquisitionClass,
    Company,
    DiscoverySource,
    JobProvenance,
    NormalizedJobOpening,
    SourceKind,
)
from nerve_center.persistence.database import Database, SCHEMA_VERSION
from nerve_center.persistence.discovery import (
    CompanyRepository,
    DiscoverySourceRepository,
    JobOpeningRepository,
)
from nerve_center.persistence.scoring import (
    CompanyEnrichmentRepository,
    JobEnrichmentRepository,
    LocationPreferencesRepository,
    OpportunityScoreRepository,
    ScoringRuleRepository,
    ScoringSettingsRepository,
)
from nerve_center.scoring.models import (
    CompanyEnrichment,
    JobEnrichment,
    LocationAssessment,
    LocationPreferences,
    LocationScope,
    OpportunityScore,
    RuleAction,
    RuleTarget,
    ScoringRule,
    ScoringSettings,
)


def test_scoring_state_and_history_persist_append_only(tmp_path: Path) -> None:
    database = Database(Settings(data_dir=tmp_path / "runtime"))
    database.initialize()
    company = Company(id="company-1", canonical_name="Example", domain="example.com")
    source = DiscoverySource(
        id="source-1",
        company_id=company.id,
        name="Manual source",
        kind=SourceKind.MANUAL,
        acquisition_class=AcquisitionClass.MANUAL_IMPORT_ONLY,
        base_url="https://example.com/jobs",
        parser_version="manual-v1",
    )
    opening = NormalizedJobOpening(
        id="job-1",
        company_id=company.id,
        company_name=company.canonical_name,
        company_domain=company.domain,
        title="Product Manager",
        description="Build analytics products.",
        source_url="https://example.com/jobs/1",
        canonical_url="https://example.com/jobs/1",
        provenance=[
            JobProvenance(
                source_id=source.id,
                connector="manual",
                parser_version="manual-v1",
                source_url="https://example.com/jobs/1",
                direct_employer_source=True,
            )
        ],
    )
    CompanyRepository(database).upsert(company)
    DiscoverySourceRepository(database).upsert(source)
    JobOpeningRepository(database).upsert(opening)

    assert LocationPreferencesRepository(database).save(LocationPreferences()).version == 1
    assert ScoringSettingsRepository(database).save(ScoringSettings()).version == 2
    CompanyEnrichmentRepository(database).save(CompanyEnrichment(company_id=company.id))
    JobEnrichmentRepository(database).save(JobEnrichment(job_id=opening.id))
    rule = ScoringRule(
        id="rule-1",
        target=RuleTarget.DOMAIN,
        action=RuleAction.PREFER,
        pattern="example.com",
    )
    ScoringRuleRepository(database).upsert(rule)

    history = OpportunityScoreRepository(database)
    base = OpportunityScore(
        id="score-1",
        job_id=opening.id,
        profile_version=1,
        contract_version="job-scout-score-v1",
        settings_version=1,
        fit=80,
        response_likelihood=75,
        opportunity_value=70,
        confidence=90,
        confidence_multiplier=1,
        base_priority=76,
        priority=76,
        location=LocationAssessment(
            scope=LocationScope.LOCAL,
            location_score=90,
            confidence=0.9,
        ),
        job_snapshot_hash="a" * 64,
        profile_snapshot_hash="b" * 64,
        calibration_key=opening.id,
    )
    history.append(base)
    history.append(base.model_copy(update={"id": "score-2", "settings_version": 2, "priority": 81}))

    assert [item.id for item in history.list(opening.id)] == ["score-2", "score-1"]
    assert ScoringRuleRepository(database).list()[0].id == rule.id
    assert SCHEMA_VERSION == 10
