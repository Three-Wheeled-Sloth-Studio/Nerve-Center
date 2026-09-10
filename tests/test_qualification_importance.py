from nerve_center.scoring.fit import required_coverage, responsibility_coverage
from nerve_center.scoring.models import (
    GateCategory,
    JobFitAnalysis,
    MatchLevel,
    QualificationAssessment,
    QualificationImportance,
)
from nerve_center.scoring.qualification_importance import normalize_qualifications


def _qualification(
    identifier: str,
    requirement: str,
    *,
    importance: QualificationImportance = QualificationImportance.REQUIRED,
    match: MatchLevel = MatchLevel.FULL,
    excerpt: str | None = None,
    weight: float = 1.0,
    rationale: list[str] | None = None,
) -> QualificationAssessment:
    return QualificationAssessment(
        id=identifier,
        importance=importance,
        requirement=requirement,
        job_excerpt=excerpt or requirement,
        match_level=match,
        confidence=0.9,
        decision_weight=weight,
        decision_weight_rationale=rationale or [],
    )


def _analysis(qualifications: list[QualificationAssessment]) -> JobFitAnalysis:
    return JobFitAnalysis(
        id="analysis",
        job_id="job",
        profile_version=1,
        contract_version="job-fit-analysis-v6",
        model="test",
        qualifications=qualifications,
    )


def test_explicit_job_language_bounds_model_hint_and_controls_weight() -> None:
    must_have = _qualification(
        "critical",
        "Own product strategy",
        excerpt="Candidates must own product strategy for the platform.",
        weight=0.5,
    )
    nice_to_have = _qualification(
        "peripheral",
        "Healthcare experience",
        excerpt="Healthcare experience is a nice to have.",
        weight=1.5,
    )

    normalized = normalize_qualifications([must_have, nice_to_have])

    assert normalized[0].decision_weight == 1.45
    assert normalized[1].decision_weight == 0.7
    assert any("must/minimum" in item for item in normalized[0].decision_weight_rationale)
    assert any("nice-to-have" in item for item in normalized[1].decision_weight_rationale)


def test_near_duplicate_requirement_is_retained_but_not_double_counted() -> None:
    required = _qualification("required", "Lead analytics products")
    duplicate = _qualification(
        "responsibility",
        "Lead enterprise analytics products",
        importance=QualificationImportance.RESPONSIBILITY,
    )

    normalized = normalize_qualifications([required, duplicate])

    assert normalized[0].duplicate_of is None
    assert normalized[1].duplicate_of == "required"
    assert responsibility_coverage(_analysis([required, duplicate])) == 0.5


def test_critical_match_outweighs_multiple_peripheral_matches() -> None:
    critical = _qualification(
        "critical",
        "Own enterprise product strategy",
        match=MatchLevel.FULL,
        weight=1.45,
        rationale=["explicit critical requirement"],
    )
    peripheral = [
        _qualification(
            f"peripheral-{index}",
            f"Supporting capability {index}",
            match=MatchLevel.NONE,
            weight=0.6,
            rationale=["supporting requirement"],
        )
        for index in range(3)
    ]
    inverse = [
        critical.model_copy(update={"match_level": MatchLevel.NONE}),
        *[item.model_copy(update={"match_level": MatchLevel.FULL}) for item in peripheral],
    ]

    central_match = required_coverage(_analysis([critical, *peripheral]))
    peripheral_matches = required_coverage(_analysis(inverse))

    assert central_match > peripheral_matches


def test_duplicate_full_match_cannot_inflate_required_coverage() -> None:
    primary = _qualification("primary", "Lead product analytics")
    duplicate = _qualification("duplicate", "Lead enterprise product analytics")
    missing = _qualification("missing", "Own pricing strategy", match=MatchLevel.NONE)

    with_duplicate = required_coverage(_analysis([primary, duplicate, missing]))
    without_duplicate = required_coverage(_analysis([primary, missing]))

    assert with_duplicate == without_duplicate


def test_missing_high_importance_requirement_remains_soft_without_factual_gate() -> None:
    item = _qualification(
        "critical",
        "Own product strategy",
        match=MatchLevel.NONE,
        weight=1.45,
        rationale=["critical job-side requirement"],
    )

    assert item.gate_category is GateCategory.NONE
    assert required_coverage(_analysis([item])) == 0.0
