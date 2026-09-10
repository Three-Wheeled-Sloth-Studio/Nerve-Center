"""Deterministic qualification decision-weight and duplicate normalization."""

from __future__ import annotations

import re
from typing import Any

from nerve_center.scoring.models import (
    GateCategory,
    MatchLevel,
    QualificationAssessment,
    QualificationImportance,
)

_MODEL_WEIGHT_MIN = 0.75
_MODEL_WEIGHT_MAX = 1.25
_IMPORTANCE_MIN = 0.5
_IMPORTANCE_MAX = 1.5
_DUPLICATE_JACCARD = 0.72

_STRONG_CUES = (
    "must",
    "minimum qualification",
    "minimum requirement",
    "essential",
    "mandatory",
    "critical",
    "core responsibility",
    "primary responsibility",
)
_MODERATE_CUES = (
    "required",
    "key responsibility",
    "responsible for",
)
_LOW_CUES = (
    "preferred",
    "nice to have",
    "nice-to-have",
    "bonus",
    "a plus",
    "plus if",
)

_STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "be",
    "for",
    "from",
    "in",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
}
_TOKEN_ALIASES = {
    "products": "product",
    "responsibilities": "responsibility",
    "requirements": "requirement",
}

_MATCH_VALUES = {
    MatchLevel.FULL: 1.0,
    MatchLevel.PARTIAL: 0.5,
    MatchLevel.NONE: 0.0,
    MatchLevel.UNKNOWN: 0.25,
}
_RESPONSIBILITY_MATCH_VALUES = {
    **_MATCH_VALUES,
    MatchLevel.UNKNOWN: 0.1,
}


def normalize_qualifications(
    qualifications: list[QualificationAssessment],
) -> list[QualificationAssessment]:
    """Return effective job-side weights and duplicate links without dropping evidence."""

    normalized = [_normalize_weight(item) for item in qualifications]
    representatives: list[int] = []
    duplicate_of: dict[int, str] = {}
    ranked = sorted(
        range(len(normalized)),
        key=lambda index: _representative_rank(normalized[index], index),
        reverse=True,
    )
    for index in ranked:
        item = normalized[index]
        duplicate = next(
            (
                rep_index
                for rep_index in representatives
                if _near_duplicate(item, normalized[rep_index])
            ),
            None,
        )
        if duplicate is None:
            representatives.append(index)
        else:
            duplicate_of[index] = normalized[duplicate].id

    return [
        item.model_copy(update={"duplicate_of": duplicate_of.get(index)})
        for index, item in enumerate(normalized)
    ]


def weighted_coverage(
    qualifications: list[QualificationAssessment],
    importance: QualificationImportance,
) -> tuple[float, list[dict[str, Any]]]:
    """Calculate match coverage weighted by employer-side decision importance."""

    normalized = normalize_qualifications(qualifications)
    values = (
        _RESPONSIBILITY_MATCH_VALUES
        if importance is QualificationImportance.RESPONSIBILITY
        else _MATCH_VALUES
    )
    rows: list[dict[str, Any]] = []
    numerator = 0.0
    denominator = 0.0
    for item in normalized:
        if item.importance is not importance:
            continue
        match_value = values[item.match_level]
        counted = item.duplicate_of is None
        contribution = item.decision_weight * match_value if counted else 0.0
        if counted:
            numerator += contribution
            denominator += item.decision_weight
        rows.append(
            {
                "id": item.id,
                "importance": item.importance.value,
                "requirement": item.requirement,
                "match_level": item.match_level.value,
                "match_value": match_value,
                "decision_weight": round(item.decision_weight, 3),
                "decision_weight_rationale": item.decision_weight_rationale,
                "duplicate_of": item.duplicate_of,
                "counted": counted,
                "weighted_contribution": round(contribution, 4),
            }
        )
    if denominator == 0:
        return 0.5, rows
    return numerator / denominator, rows


def coverage_breakdown(
    qualifications: list[QualificationAssessment],
) -> dict[str, Any]:
    """Return reconstructable weighted coverage and per-qualification inputs."""

    required, required_rows = weighted_coverage(
        qualifications, QualificationImportance.REQUIRED
    )
    responsibilities, responsibility_rows = weighted_coverage(
        qualifications, QualificationImportance.RESPONSIBILITY
    )
    preferred, preferred_rows = weighted_coverage(
        qualifications, QualificationImportance.PREFERRED
    )
    return {
        "required": required,
        "responsibility": responsibilities,
        "preferred": preferred,
        "qualifications": [
            *required_rows,
            *responsibility_rows,
            *preferred_rows,
        ],
    }


def _normalize_weight(item: QualificationAssessment) -> QualificationAssessment:
    text = f"{item.requirement} {item.job_excerpt}".casefold()
    if item.decision_weight_rationale:
        weight = item.decision_weight
        rationale = list(item.decision_weight_rationale)
    else:
        weight = min(_MODEL_WEIGHT_MAX, max(_MODEL_WEIGHT_MIN, item.decision_weight))
        rationale = []
        if abs(item.decision_weight - 1.0) > 0.001:
            rationale.append(
                f"Model job-centrality hint bounded to {weight:.2f}; candidate match did not affect it."
            )

    if any(cue in text for cue in _STRONG_CUES):
        weight = max(weight, 1.45)
        rationale.append("Explicit must/minimum/essential/core job language raised importance.")
    elif any(cue in text for cue in _MODERATE_CUES):
        weight = max(weight, 1.25)
        rationale.append("Explicit required/key-responsibility job language raised importance.")

    if any(cue in text for cue in _LOW_CUES):
        weight = min(weight, 0.7)
        rationale.append("Explicit preferred/nice-to-have/bonus job language lowered importance.")

    weight = min(_IMPORTANCE_MAX, max(_IMPORTANCE_MIN, weight))
    if not rationale:
        rationale.append("No explicit centrality cue; neutral job-side decision weight retained.")
    return item.model_copy(
        update={
            "decision_weight": round(weight, 3),
            "decision_weight_rationale": list(dict.fromkeys(rationale)),
            "duplicate_of": None,
        }
    )


def _representative_rank(
    item: QualificationAssessment,
    index: int,
) -> tuple[int, int, float, float, int]:
    category_rank = {
        QualificationImportance.REQUIRED: 3,
        QualificationImportance.RESPONSIBILITY: 2,
        QualificationImportance.PREFERRED: 1,
    }[item.importance]
    return (
        1 if item.gate_category is not GateCategory.NONE else 0,
        category_rank,
        item.decision_weight,
        item.confidence,
        -index,
    )


def _near_duplicate(
    left: QualificationAssessment,
    right: QualificationAssessment,
) -> bool:
    left_tokens = _tokens(left.requirement)
    right_tokens = _tokens(right.requirement)
    if len(left_tokens) < 2 or len(right_tokens) < 2:
        return False
    overlap = len(left_tokens & right_tokens)
    union = len(left_tokens | right_tokens)
    jaccard = overlap / max(1, union)
    containment = overlap / max(1, min(len(left_tokens), len(right_tokens)))
    return jaccard >= _DUPLICATE_JACCARD or (containment >= 0.85 and jaccard >= 0.5)


def _tokens(value: str) -> set[str]:
    tokens = set()
    for token in re.findall(r"[a-z0-9]+", value.casefold()):
        if token in _STOPWORDS or len(token) <= 2:
            continue
        tokens.add(_TOKEN_ALIASES.get(token, token))
    return tokens
