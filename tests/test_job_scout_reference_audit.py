from pathlib import Path

from nerve_center.config import Settings
from nerve_center.persistence.database import Database
from nerve_center.plugins.job_scout.bootstrap import _recent_reference_attempt_evidence
from nerve_center.plugins.job_scout.discovery_learning import StrategyOutcome
from nerve_center.plugins.job_scout.discovery_quality import DiscoveryQualityRepository


def _learning(tmp_path: Path) -> DiscoveryQualityRepository:
    database = Database(Settings(data_dir=tmp_path / "runtime"))
    database.initialize()
    return DiscoveryQualityRepository(database)


def test_reference_attempt_evidence_is_bounded_and_run_attributed(tmp_path: Path) -> None:
    learning = _learning(tmp_path)
    strategy = learning.ensure_strategy(
        {
            "kind": "public_search",
            "hypothesis_family": "local_employer",
            "anchor": "major employers",
            "location": "Example Metro, NC",
            "source_domain": "web",
        },
        origin="fixture",
    )
    learning.record_attempt(
        "run-reference",
        4,
        strategy.id,
        "expand",
        StrategyOutcome(
            detail={
                "stages": {
                    "search_results_returned": 7,
                    "reference_pages_inspected": 1,
                    "reference_fetches_deferred": 1,
                    "reference_selection_evidence": [
                        {
                            "url": "https://partnership.example.org/major-employers",
                            "title": "Major Employers",
                            "selected": True,
                            "intent_tier": 0,
                            "authority_tier": 1,
                            "supported_document": False,
                        }
                    ],
                    "employer_reference_evidence": [
                        {
                            "url": "https://partnership.example.org/major-employers",
                            "status": "inspected",
                            "candidate_count": 3,
                        }
                    ],
                    "attachment_reference_evidence": [],
                }
            }
        ),
    )
    other = learning.ensure_strategy(
        {"kind": "public_search", "anchor": "product leadership"},
        origin="fixture",
    )
    learning.record_attempt(
        "run-other",
        5,
        other.id,
        "expand",
        StrategyOutcome(detail={"stages": {"search_results_returned": 2}}),
    )

    rows = _recent_reference_attempt_evidence(learning, limit=1)

    assert len(rows) == 1
    row = rows[0]
    assert row["run_id"] == "run-reference"
    assert row["strategy_id"] == strategy.id
    assert row["cycle"] == 4
    assert row["hypothesis_family"] == "local_employer"
    assert row["location"] == "Example Metro, NC"
    assert row["anchor"] == "major employers"
    assert row["search_results_returned"] == 7
    assert row["reference_pages_inspected"] == 1
    assert row["reference_fetches_deferred"] == 1
    selection = row["reference_selection_evidence"]
    assert isinstance(selection, list)
    assert selection[0]["selected"] is True
    references = row["employer_reference_evidence"]
    assert isinstance(references, list)
    assert references[0]["candidate_count"] == 3
