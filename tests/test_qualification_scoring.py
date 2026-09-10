from nerve_center.scoring.engine import SCORING_ENGINE_VERSION, _fit_score
from nerve_center.scoring.models import (
    JobFitAnalysis,
    MatchLevel,
    QualificationAssessment,
    QualificationImportance,
    ScoreFactor,
)


def _qualification(
    identifier: str,
    requirement: str,
    match: MatchLevel,
    weight: float,
) -> QualificationAssessment:
    return QualificationAssessment(
        id=identifier,
        importance=QualificationImportance.REQUIRED,
        requirement=requirement,
        job_excerpt=requirement,
        match_level=match,
        confidence=0.9,
        decision_weight=weight,
        decision_weight_rationale=["test job-side importance"],
    )


def _analysis(qualifications: list[QualificationAssessment]) -> JobFitAnalysis:
    return JobFitAnalysis(
        id="analysis",
        job_id="job",
        profile_version=1,
        contract_version="job-fit-analysis-v6",
        model="legacy",
        qualifications=qualifications,
        seniority_score=60,
        domain_score=48,
        leadership_score=60,
        methods_score=60,
        outcomes_score=60,
        confidence=0.8,
    )


def test_fit_factor_exposes_weighted_inputs_and_central_match_ordering() -> None:
    central = _qualification(
        "central",
        "Own enterprise product strategy",
        MatchLevel.FULL,
        1.45,
    )
    peripheral = [
        _qualification(
            f"peripheral-{index}",
            f"Supporting capability {index}",
            MatchLevel.NONE,
            0.6,
        )
        for index in range(2)
    ]
    inverse = [
        central.model_copy(update={"match_level": MatchLevel.NONE}),
        *[item.model_copy(update={"match_level": MatchLevel.FULL}) for item in peripheral],
    ]
    central_factors: list[ScoreFactor] = []
    inverse_factors: list[ScoreFactor] = []

    central_fit, central_required, _, _ = _fit_score(
        _analysis([central, *peripheral]), central_factors
    )
    inverse_fit, inverse_required, _, _ = _fit_score(
        _analysis(inverse), inverse_factors
    )

    assert SCORING_ENGINE_VERSION == "job-scout-ranking-v5"
    assert central_required > inverse_required
    assert central_fit > inverse_fit
    factor = next(item for item in central_factors if item.code == "fit_components")
    rows = factor.detail["qualification_coverage"]
    central_row = next(item for item in rows if item["id"] == "central")
    assert central_row["decision_weight"] == 1.45
    assert central_row["weighted_contribution"] == 1.45
    assert central_row["decision_weight_rationale"] == ["test job-side importance"]
