from __future__ import annotations

import runpy
from pathlib import Path
from typing import Any

_SCRIPT = runpy.run_path(str(Path(__file__).parents[1] / "scripts" / "agent_context.py"))
GitContext = _SCRIPT["GitContext"]
build_packet = _SCRIPT["build_packet"]
infer_issue = _SCRIPT["_infer_issue"]


def _write_fixture(repo: Path) -> None:
    (repo / "refs/planning").mkdir(parents=True)
    (repo / "refs/handoffs").mkdir(parents=True)
    (repo / "refs/implementation").mkdir(parents=True)
    (repo / "refs/testing").mkdir(parents=True)
    (repo / "refs/project.yaml").write_text(
        """identity:
  name: Nerve Center
  current_phase: Ranking quality
""",
        encoding="utf-8",
    )
    (repo / "refs/planning/decision-register.md").write_text(
        """| ID | Status | Decision |
|---|---|---|
| NC-001 | accepted | Nerve Center is local-first. |
| NC-047 | accepted | Job Scout fit is responsibility- and evidence-first, with direct domain above adjacent domain and transferable experience. |
""",
        encoding="utf-8",
    )
    (repo / "refs/handoffs/currentHandoff.md").write_text(
        """# Current Handoff

## Active product correction

The remaining ranking gap is explicit domain-distance evidence for responsibility-level fit.

A completely unrelated desktop note should not outrank the fit work.

## Architectural constraints

- Modules remain model-blind.

## Read before implementation

1. A very large document that should not be copied into the packet.
""",
        encoding="utf-8",
    )
    (repo / "refs/implementation/fileMap.yaml").write_text(
        """common_tasks:
  - task: Change Job Scout fit or scoring
    look_in: [src/nerve_center/scoring, src/nerve_center/profile, refs/planning/job-scout-scoring-contract.md]
  - task: Change desktop UI
    look_in: [desktop/src]
""",
        encoding="utf-8",
    )
    (repo / "refs/testing/validationCommands.yaml").write_text(
        """commands:
  - id: python-tests
    command: pytest
    required: true
  - id: windows-package
    command: package-everything
    required: release-checkpoint
""",
        encoding="utf-8",
    )


def test_packet_selects_relevant_context_and_stays_bounded(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    packet = build_packet(
        tmp_path,
        focus="Job Scout responsibility domain fit scoring",
        issue=24,
        git_context=GitContext(
            branch="agent/24-agent-context-packet",
            head="abc123def456",
            changed_paths=("src/nerve_center/scoring/fit.py",),
            dirty_paths=("tests/test_fit_analysis.py",),
        ),
        max_decisions=1,
    )

    assert "Branch: `agent/24-agent-context-packet`" in packet
    assert "HEAD: `abc123def456`" in packet
    assert "Issue: #24" in packet
    assert "NC-047" in packet
    assert "NC-001" not in packet
    assert "explicit domain-distance evidence" in packet
    assert "`src/nerve_center/scoring`" in packet
    assert "`src/nerve_center/scoring/fit.py`" in packet
    assert "`tests/test_fit_analysis.py`" in packet
    assert "`python-tests` — `pytest`" in packet
    assert "package-everything" not in packet
    assert "very large document" not in packet
    assert len(packet) < 8_000


def test_packet_without_focus_uses_recent_accepted_decision(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    packet = build_packet(
        tmp_path,
        git_context=GitContext(branch="dev", head="abc123"),
        max_decisions=1,
        max_handoff_snippets=1,
    )

    assert "NC-047" in packet


def test_issue_number_is_inferred_from_agent_branch() -> None:
    assert infer_issue("agent/24-agent-context-packet") == 24
    assert infer_issue("codex/105-fix") == 105
    assert infer_issue("dev") is None
