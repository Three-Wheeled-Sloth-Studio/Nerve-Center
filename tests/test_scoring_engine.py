from datetime import UTC, datetime, timedelta

from nerve_center.discovery.models import (
    JobProvenance,
    NormalizedJobOpening,
    WorkArrangement,
)
from nerve_center.profile.models import CanonicalCareerProfile
from nerve_center.scoring.engine import OpportunityScorer
from nerve_center.scoring.models import (
    CompanyEnrichment,
    GateCategory,
    GeoPoint,
    JobEnrichment,
    JobFitAnalysis,
    LocationPreferences,
    LocationScope,
    MatchLevel,
    OfficeLocation,
    QualificationAssessment,
    QualificationImportance,
    RuleAction,
    RuleTarget,
    ScoringRule,
    ScoringSettings,
    ScoringWeights,
)


def _opening(
    arrangement: WorkArrangement = WorkArrangement.HYBRID,
    posted_at: datetime | None = None,
) -> NormalizedJobOpening:
    return NormalizedJobOpening(
        id="job-1",
        company_id="company-1",
        company_name="Example Co",
        company_domain="example.com",
        title="Product Analytics Director",
        description="Lead product analytics and workflow automation. " * 20,
        location_text="Greensboro, NC",
        work_arrangement=arrangement,
        employment_type="Full-time",
        source_url="https://example.com/jobs/1",
        canonical_url="https://example.com/jobs/1",
        posted_at=posted_at,
        provenance=[
            JobProvenance(
                source_id="source-1",
                connector="greenhouse",
                parser_version="v1",
                source_url="https://example.com/jobs/1",
                direct_employer_source=True,
            )
        ],
    )


def _analysis(
    match: MatchLevel = MatchLevel.FULL,
    gate: GateCategory = GateCategory.NONE,
) -> JobFitAnalysis:
    return JobFitAnalysis(
        id="analysis-1",
        job_id="job-1",
        profile_version=1,
        contract_version="job-fit-analysis-v1",
        model="fake",
        qualifications=[
            QualificationAssessment(
                id="qualification-1",
                importance=QualificationImportance.REQUIRED,
                requirement="Lead product analytics",
                job_excerpt="Lead product analytics",
                matched_claim_ids=["claim-1"] if match is not MatchLevel.NONE else [],
                match_level=match,
                confidence=0.95,
                gate_category=gate,
            )
        ],
        seniority_score=90,
        domain_score=90,
        leadership_score=90,
        methods_score=85,
        outcomes_score=85,
        confidence=0.95,
    )


def _score(
    *,
    opening: NormalizedJobOpening | None = None,
    analysis: JobFitAnalysis | None = None,
    company: CompanyEnrichment | None = None,
    job: JobEnrichment | None = None,
    preferences: LocationPreferences | None = None,
    settings: ScoringSettings | None = None,
    rules: list[ScoringRule] | None = None,
    target_title_alignment: float | None = None,
):
    return OpportunityScorer().score(
        opening=opening or _opening(posted_at=datetime.now(UTC) - timedelta(days=1)),
        profile=CanonicalCareerProfile(version=1),
        fit_analysis=analysis or _analysis(),
        company_enrichment=company or CompanyEnrichment(company_id="company-1"),
        job_enrichment=job or JobEnrichment(job_id="job-1", commute_minutes=20),
        location_preferences=preferences or LocationPreferences(home_region="NC"),
        settings=settings or ScoringSettings(),
        rules=rules or [],
        target_title_alignment=target_title_alignment,
        now=datetime.now(UTC),
    )


def test_closer_local_role_has_higher_response_score() -> None:
    close = _score(job=JobEnrichment(job_id="job-1", commute_minutes=20))
    far = _score(job=JobEnrichment(job_id="job-1", commute_minutes=85))

    assert close.location.scope is LocationScope.LOCAL
    assert close.response_likelihood > far.response_likelihood


def test_distant_remote_penalty_requires_exceptional_match() -> None:
    opening = _opening(
        arrangement=WorkArrangement.REMOTE,
        posted_at=datetime.now(UTC) - timedelta(days=1),
    )
    weak = _score(
        opening=opening,
        analysis=_analysis(match=MatchLevel.PARTIAL),
        job=JobEnrichment(job_id="job-1", region="TX", location_confidence=0.9),
    )
    strong = _score(
        opening=opening,
        job=JobEnrichment(job_id="job-1", region="TX", location_confidence=0.9),
    )

    assert weak.location.scope is LocationScope.DISTANT
    assert strong.response_likelihood > weak.response_likelihood
    assert any(item.code == "distant_remote_saturation" for item in weak.factors)


def test_hard_include_retains_but_does_not_hide_factual_gate() -> None:
    result = _score(
        job=JobEnrichment(job_id="job-1", relocation_required=True),
        rules=[
            ScoringRule(
                id="include-1",
                target=RuleTarget.DOMAIN,
                action=RuleAction.HARD_INCLUDE,
                pattern="example.com",
            )
        ],
    )

    assert result.excluded is True
    assert result.retained is True
    assert result.priority >= 60
    assert any(item.code == "relocation_required" for item in result.gates)


def test_missing_dates_and_evergreen_signals_are_explained() -> None:
    result = _score(
        opening=_opening(posted_at=None),
        job=JobEnrichment(
            job_id="job-1",
            commute_minutes=20,
            repost_signal=True,
            evergreen_signal=True,
            conflicting_source_data=True,
        ),
    )
    codes = {item.code for item in result.factors}

    assert {
        "listing_date_missing",
        "repost_signal",
        "evergreen_signal",
        "conflicting_source_data",
    }.issubset(codes)


def test_nearby_relevant_office_improves_remote_response() -> None:
    opening = _opening(
        arrangement=WorkArrangement.REMOTE,
        posted_at=datetime.now(UTC) - timedelta(days=1),
    )
    preferences = LocationPreferences(
        home_point=GeoPoint(latitude=36.0726, longitude=-79.7920),
        home_region="NC",
        regional_regions=["NC", "VA", "SC"],
    )
    job = JobEnrichment(job_id="job-1", region="TX", location_confidence=0.9)
    with_office = _score(
        opening=opening,
        job=job,
        preferences=preferences,
        company=CompanyEnrichment(
            company_id="company-1",
            offices=[
                OfficeLocation(
                    id="office-1",
                    label="Greensboro office",
                    point=GeoPoint(latitude=36.1, longitude=-79.8),
                )
            ],
        ),
    )
    without_office = _score(opening=opening, job=job, preferences=preferences)

    assert with_office.location.scope is LocationScope.LOCAL
    assert with_office.response_likelihood > without_office.response_likelihood


def test_textual_local_company_presence_improves_remote_response_with_evidence() -> None:
    opening = _opening(
        arrangement=WorkArrangement.REMOTE,
        posted_at=datetime.now(UTC) - timedelta(days=1),
    )
    preferences = LocationPreferences(
        local_markets=["Greensboro, NC"],
        home_region="NC",
    )
    with_presence = _score(
        opening=opening,
        job=JobEnrichment(job_id="job-1", region="TX", location_confidence=0.9),
        preferences=preferences,
        company=CompanyEnrichment(
            company_id="company-1",
            offices=[
                OfficeLocation(
                    id="presence-1",
                    label="Greensboro, NC",
                    region="NC",
                    evidence_url="https://example.com/jobs/nearby",
                    confidence=0.8,
                )
            ],
        ),
    )
    without_presence = _score(
        opening=opening,
        job=JobEnrichment(job_id="job-1", region="TX", location_confidence=0.9),
        preferences=preferences,
    )

    factor = next(
        item for item in with_presence.factors if item.code == "local_company_presence"
    )
    assert with_presence.location.scope is LocationScope.LOCAL
    assert with_presence.response_likelihood > without_presence.response_likelihood
    assert factor.evidence == ["https://example.com/jobs/nearby"]


def test_unverified_required_license_creates_visible_gate() -> None:
    result = _score(analysis=_analysis(match=MatchLevel.NONE, gate=GateCategory.LICENSE))

    assert result.excluded is True
    assert any(item.code.startswith("required_license:") for item in result.gates)


def test_priority_uses_configured_component_weights() -> None:
    fit_heavy = _score(
        settings=ScoringSettings(
            weights=ScoringWeights(fit=1, response_likelihood=0, opportunity_value=0)
        )
    )
    response_heavy = _score(
        settings=ScoringSettings(
            weights=ScoringWeights(fit=0, response_likelihood=1, opportunity_value=0)
        )
    )

    assert fit_heavy.base_priority == fit_heavy.fit
    assert response_heavy.base_priority == response_heavy.response_likelihood


def test_target_title_alignment_is_only_a_weak_visible_fit_clue() -> None:
    aligned = _score(target_title_alignment=1.0)
    unrelated = _score(target_title_alignment=0.0)

    assert aligned.fit - unrelated.fit == 6.0
    assert unrelated.fit > 20.0
    assert unrelated.priority < aligned.priority
    assert any(item.code == "target_title_alignment" for item in unrelated.factors)
    assert unrelated.calculation["target_title_alignment"] == 0.0
    assert unrelated.calculation["scoring_engine_version"] == "job-scout-ranking-v3"
