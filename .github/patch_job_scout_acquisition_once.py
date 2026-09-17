from pathlib import Path
import re


learning_path = Path("src/nerve_center/plugins/job_scout/discovery_learning.py")
learning = learning_path.read_text(encoding="utf-8")

helper_pattern = re.compile(
    r"def _employer_deepening_evidence_is_current\(dimensions: dict\[str, str\]\) -> bool:\n.*?\n\ndef _canonical_public_search_ids\(",
    re.DOTALL,
)
helper_replacement = '''def _employer_deepening_evidence_priority(dimensions: dict[str, str]) -> int:
    """Rank equivalent employer hypotheses by evidence-semantics freshness."""

    if dimensions.get("hypothesis_family") != "local_employer_deepen":
        return 0
    authority = dimensions.get("employer_evidence_authority", "")
    medium = dimensions.get("employer_evidence_medium", "")
    extraction_method = dimensions.get("employer_evidence_extraction_method", "")
    if (
        medium == "attachment"
        or dimensions.get("employer_evidence_revision")
        == EMPLOYER_LANDSCAPE_EVIDENCE_REVISION
    ):
        return 2
    if (
        authority == "civic_attachment"
        or extraction_method.startswith(("pdf_", "attachment_"))
    ):
        return 1
    return 0


def _employer_deepening_evidence_is_current(dimensions: dict[str, str]) -> bool:
    return _employer_deepening_evidence_priority(dimensions) > 0


def _canonical_public_search_ids('''
learning, count = helper_pattern.subn(helper_replacement, learning, count=1)
if count != 1:
    raise SystemExit(f"expected one employer-evidence helper block, found {count}")

canonical_pattern = re.compile(
    r"        existing = canonical\.get\(identity\)\n.*?            canonical\[identity\] = model\n(?=    return \{\*retained)",
    re.DOTALL,
)
canonical_replacement = '''        existing = canonical.get(identity)
        model_is_current_semantics = (
            (
                model.dimensions.get("hypothesis_family")
                in {"local_employer", "regional_alias_probe"}
                and model.dimensions.get("query_revision")
                == MARKET_REFERENCE_QUERY_REVISION
            )
            or _employer_deepening_evidence_is_current(model.dimensions)
        )
        existing_is_current_semantics = (
            existing is not None
            and (
                (
                    existing.dimensions.get("hypothesis_family")
                    in {"local_employer", "regional_alias_probe"}
                    and existing.dimensions.get("query_revision")
                    == MARKET_REFERENCE_QUERY_REVISION
                )
                or _employer_deepening_evidence_is_current(existing.dimensions)
            )
        )
        both_employer_deepening = (
            existing is not None
            and model.dimensions.get("hypothesis_family") == "local_employer_deepen"
            and existing.dimensions.get("hypothesis_family") == "local_employer_deepen"
        )
        model_evidence_priority = _employer_deepening_evidence_priority(model.dimensions)
        existing_evidence_priority = (
            _employer_deepening_evidence_priority(existing.dimensions)
            if existing is not None
            else 0
        )
        if (
            existing is None
            or (
                both_employer_deepening
                and model_evidence_priority > existing_evidence_priority
            )
            or (
                both_employer_deepening
                and model_evidence_priority == existing_evidence_priority
                and (model.created_at, model.id) < (existing.created_at, existing.id)
            )
            or (
                not both_employer_deepening
                and model_is_current_semantics
                and not existing_is_current_semantics
            )
            or (
                not both_employer_deepening
                and model_is_current_semantics == existing_is_current_semantics
                and (model.created_at, model.id) < (existing.created_at, existing.id)
            )
        ):
            canonical[identity] = model
'''
learning, count = canonical_pattern.subn(canonical_replacement, learning, count=1)
if count != 1:
    raise SystemExit(f"expected one canonical public-search block, found {count}")
learning_path.write_text(learning, encoding="utf-8")

fetching_path = Path("src/nerve_center/discovery/fetching.py")
fetching = fetching_path.read_text(encoding="utf-8")
marker_anchor = '    "security challenge",\n'
extra_markers = (
    '    "unfortunately, bots use duckduckgo too",\n'
    '    "bots, we have detected",\n'
    '    "robot-detected",\n'
    '    "select all squares containing a duck",\n'
)
if extra_markers[0] not in fetching:
    if marker_anchor not in fetching:
        raise SystemExit("challenge marker insertion point not found")
    fetching = fetching.replace(marker_anchor, marker_anchor + "".join(extra_markers), 1)
fetching_path.write_text(fetching, encoding="utf-8")

learning_test_path = Path("tests/test_job_scout_discovery_learning.py")
learning_test = learning_test_path.read_text(encoding="utf-8")
regression = r'''


def test_normalized_attachment_evidence_bypasses_legacy_equivalent_cooldown(
    tmp_path: Path,
) -> None:
    learning = JobScoutDiscoveryRepository(_database(tmp_path))
    attempted_at = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)
    legacy = learning.ensure_strategy(
        {
            "kind": "public_search",
            "hypothesis_family": "local_employer_deepen",
            "anchor": "Example Mobility",
            "location": "Example, NC",
            "source_domain": "web",
            "employer_evidence_authority": "civic_attachment",
            "employer_evidence_extraction_method": "pdf_ocr_ranked_employers",
        },
        origin="public_employer_attachment_evidence",
    )
    learning.record_attempt(
        "prior-run",
        1,
        legacy.id,
        "deepen",
        StrategyOutcome(),
        finished_at=attempted_at,
    )
    normalized = learning.ensure_strategy(
        {
            "kind": "public_search",
            "hypothesis_family": "local_employer_deepen",
            "anchor": "Example Mobility",
            "location": "Example Metro Area",
            "source_domain": "web",
            "employer_evidence_authority": "civic_attachment",
            "employer_evidence_medium": "attachment",
            "employer_evidence_extraction_method": "pdf_ocr_ranked_employers",
        },
        origin="public_employer_attachment_evidence",
    )

    selected = learning.select_strategies(
        "current-run",
        limit=4,
        exploration_floor=0.25,
        revisit_after_seconds=86400,
        now=attempted_at + timedelta(minutes=5),
    )
    selected_ids = {item.id for item in selected}

    assert normalized.id in selected_ids
    assert legacy.id not in selected_ids
'''
if "test_normalized_attachment_evidence_bypasses_legacy_equivalent_cooldown" not in learning_test:
    learning_test_path.write_text(learning_test.rstrip() + regression + "\n", encoding="utf-8")

connector_test_path = Path("tests/test_discovery_connectors.py")
connector_test = connector_test_path.read_text(encoding="utf-8")
challenge_test = r'''


def test_http_fetcher_detects_duckduckgo_bot_challenge() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text=(
                "<html><body>Unfortunately, bots use DuckDuckGo too. "
                "Please complete the following challenge. "
                "Select all squares containing a duck:</body></html>"
            ),
            headers={"content-type": "text/html; charset=UTF-8"},
            request=request,
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    response = asyncio.run(
        HttpFetcher(client=client).get(
            "https://html.duckduckgo.com/html/",
            params={"q": "example"},
        )
    )
    asyncio.run(client.aclose())

    assert response.status_code == 200
    assert response.challenged is True
'''
if "test_http_fetcher_detects_duckduckgo_bot_challenge" not in connector_test:
    connector_test_path.write_text(connector_test.rstrip() + challenge_test + "\n", encoding="utf-8")
