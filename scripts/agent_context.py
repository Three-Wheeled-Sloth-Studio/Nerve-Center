"""Generate a compact, derived context packet for Nerve Center coding-agent sessions."""

from __future__ import annotations

import argparse
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as error:  # pragma: no cover - developer setup guard
    raise SystemExit("PyYAML is required; install the repository dev dependencies.") from error

DEFAULT_MAX_CHARS = 8_000
DEFAULT_MAX_DECISIONS = 8
DEFAULT_MAX_HANDOFF_SNIPPETS = 6
DEFAULT_MAX_CHANGED_PATHS = 12

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_DECISION_RE = re.compile(r"^\|\s*(NC-\d+)\s*\|\s*([^|]+?)\s*\|\s*(.*?)\s*\|\s*$")
_HEADING_RE = re.compile(r"^##\s+(.+?)\s*$")
_STOPWORDS = {
    "add",
    "agent",
    "and",
    "change",
    "code",
    "current",
    "for",
    "from",
    "into",
    "issue",
    "make",
    "the",
    "this",
    "tool",
    "use",
    "with",
    "work",
}


@dataclass(frozen=True)
class GitContext:
    branch: str
    head: str
    changed_paths: tuple[str, ...] = ()
    dirty_paths: tuple[str, ...] = ()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _run_git(repo_root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            capture_output=True,
            check=False,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def collect_git_context(repo_root: Path, base_ref: str = "dev") -> GitContext:
    branch = _run_git(repo_root, "branch", "--show-current") or "detached"
    head = _run_git(repo_root, "rev-parse", "--short=12", "HEAD") or "unknown"
    status = _run_git(repo_root, "status", "--short") or ""
    dirty_paths = tuple(
        line[3:].strip()
        for line in status.splitlines()
        if len(line) > 3 and line[3:].strip()
    )
    changed = ""
    if branch != base_ref:
        changed = _run_git(repo_root, "diff", "--name-only", f"{base_ref}...HEAD") or ""
    changed_paths = tuple(line.strip() for line in changed.splitlines() if line.strip())
    return GitContext(
        branch=branch,
        head=head,
        changed_paths=changed_paths,
        dirty_paths=dirty_paths,
    )


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in _TOKEN_RE.findall(value.casefold())
        if len(token) > 2 and token not in _STOPWORDS
    }


def _relevance(value: str, focus_tokens: set[str]) -> int:
    if not focus_tokens:
        return 0
    candidate = _tokens(value)
    return len(candidate & focus_tokens)


def _read_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _decisions(path: Path, focus_tokens: set[str], limit: int) -> list[tuple[str, str]]:
    accepted: list[tuple[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = _DECISION_RE.match(line)
        if match is None:
            continue
        decision_id, status, decision = match.groups()
        if status.strip().casefold() == "accepted":
            accepted.append((decision_id, decision.strip()))
    ranked = sorted(
        accepted,
        key=lambda item: (_relevance(f"{item[0]} {item[1]}", focus_tokens), item[0]),
        reverse=True,
    )
    if focus_tokens:
        matched = [item for item in ranked if _relevance(item[1], focus_tokens) > 0]
        if matched:
            return matched[:limit]
    return ranked[:limit]


def _markdown_blocks(path: Path) -> list[tuple[str, str]]:
    section = "Overview"
    blocks: list[tuple[str, str]] = []
    paragraph: list[str] = []

    def flush() -> None:
        if paragraph:
            text = " ".join(item.strip() for item in paragraph if item.strip()).strip()
            if text:
                blocks.append((section, text))
            paragraph.clear()

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        heading = _HEADING_RE.match(line)
        if heading:
            flush()
            section = heading.group(1)
            continue
        if not line or line == "---" or line.startswith(("type:", "title:", "description:", "status:", "tags:")):
            flush()
            continue
        if line.startswith("# "):
            flush()
            continue
        if line.startswith(('- ', '* ')):
            flush()
            blocks.append((section, line[2:].strip()))
            continue
        if re.match(r"^\d+\.\s+", line):
            flush()
            blocks.append((section, re.sub(r"^\d+\.\s+", "", line)))
            continue
        if line.startswith("```"):
            continue
        paragraph.append(line)
    flush()
    return blocks


def _handoff_snippets(
    path: Path,
    focus_tokens: set[str],
    limit: int,
) -> list[tuple[str, str]]:
    excluded_sections = {"Read before implementation", "Validation boundary"}
    blocks = [item for item in _markdown_blocks(path) if item[0] not in excluded_sections]
    section_priority = {
        "Active product correction": 4,
        "Immediate implementation slice": 3,
        "Architectural constraints": 2,
        "Current state": 1,
    }
    ranked = sorted(
        enumerate(blocks),
        key=lambda indexed: (
            _relevance(indexed[1][1], focus_tokens) * 10
            + section_priority.get(indexed[1][0], 0),
            indexed[0],
        ),
        reverse=True,
    )
    if focus_tokens:
        matched = [
            item
            for _index, item in ranked
            if _relevance(item[1], focus_tokens) > 0
        ]
        if matched:
            return matched[:limit]
    preferred = [
        item
        for _index, item in ranked
        if item[0] in {"Active product correction", "Immediate implementation slice"}
    ]
    return preferred[:limit]


def _truncate(value: str, limit: int = 360) -> str:
    normalized = " ".join(value.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1].rstrip() + "…"


def _file_hints(path: Path, focus_tokens: set[str]) -> list[tuple[str, list[str]]]:
    payload = _read_yaml(path)
    tasks = payload.get("common_tasks") or []
    ranked: list[tuple[int, str, list[str]]] = []
    for item in tasks:
        if not isinstance(item, dict):
            continue
        task = str(item.get("task") or "").strip()
        look_in = [str(value) for value in (item.get("look_in") or [])]
        score = _relevance(f"{task} {' '.join(look_in)}", focus_tokens)
        ranked.append((score, task, look_in))
    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    if focus_tokens and any(score > 0 for score, _task, _paths in ranked):
        return [(task, paths) for score, task, paths in ranked if score > 0][:3]
    return [(task, paths) for _score, task, paths in ranked[:2]]


def _validation_commands(path: Path) -> list[tuple[str, str]]:
    payload = _read_yaml(path)
    result: list[tuple[str, str]] = []
    for item in payload.get("commands") or []:
        if not isinstance(item, dict) or item.get("required") is not True:
            continue
        result.append((str(item.get("id") or "validation"), str(item.get("command") or "")))
    return result


def _project_summary(path: Path) -> tuple[str, str]:
    payload = _read_yaml(path)
    identity = payload.get("identity") or {}
    name = str(identity.get("name") or "Nerve Center")
    phase = str(identity.get("current_phase") or "unknown")
    return name, phase


def _infer_issue(branch: str) -> int | None:
    match = re.match(r"(?:agent|codex)/(\d+)(?:-|$)", branch)
    return int(match.group(1)) if match else None


def build_packet(
    repo_root: Path,
    *,
    focus: str = "",
    issue: int | None = None,
    base_ref: str = "dev",
    git_context: GitContext | None = None,
    max_decisions: int = DEFAULT_MAX_DECISIONS,
    max_handoff_snippets: int = DEFAULT_MAX_HANDOFF_SNIPPETS,
    max_changed_paths: int = DEFAULT_MAX_CHANGED_PATHS,
) -> str:
    git = git_context or collect_git_context(repo_root, base_ref=base_ref)
    issue_number = issue or _infer_issue(git.branch)
    focus_tokens = _tokens(focus)
    project_name, phase = _project_summary(repo_root / "refs/project.yaml")
    decisions = _decisions(
        repo_root / "refs/planning/decision-register.md",
        focus_tokens,
        max_decisions,
    )
    snippets = _handoff_snippets(
        repo_root / "refs/handoffs/currentHandoff.md",
        focus_tokens,
        max_handoff_snippets,
    )
    file_hints = _file_hints(repo_root / "refs/implementation/fileMap.yaml", focus_tokens)
    validation = _validation_commands(repo_root / "refs/testing/validationCommands.yaml")

    lines = [
        f"# {project_name} — Generated Agent Context",
        "",
        "> Derived orientation only. Authoritative refs/source remain the source of truth; do not edit this packet as project state.",
        "",
        "## Session",
        f"- Branch: `{git.branch}`",
        f"- HEAD: `{git.head}`",
        f"- Base ref: `{base_ref}`",
        f"- Current phase: {phase}",
    ]
    if issue_number is not None:
        lines.append(f"- Issue: #{issue_number}")
    if focus.strip():
        lines.append(f"- Focus: {focus.strip()}")

    changed = list(dict.fromkeys([*git.changed_paths, *git.dirty_paths]))
    if changed:
        lines.extend(["", "## Changed paths"])
        for item in changed[:max_changed_paths]:
            lines.append(f"- `{item}`")
        if len(changed) > max_changed_paths:
            lines.append(f"- … {len(changed) - max_changed_paths} more")

    lines.extend(["", "## Current handoff highlights"])
    for section, text in snippets:
        lines.append(f"- **{section}:** {_truncate(text)}")

    lines.extend(["", "## Relevant accepted decisions"])
    for decision_id, decision in decisions:
        lines.append(f"- **{decision_id}:** {_truncate(decision, 300)}")

    lines.extend(["", "## File-map hints"])
    for task, paths in file_hints:
        lines.append(f"- **{task}:** " + ", ".join(f"`{item}`" for item in paths))

    lines.extend(["", "## Required validation"])
    for command_id, command in validation:
        lines.append(f"- `{command_id}` — `{command}`")

    lines.extend(
        [
            "",
            "## Context discipline",
            "- Start with the paths above; use targeted search/line ranges before whole-file reads.",
            "- Treat accepted decisions as inputs. Reopen them only when new runtime/test evidence contradicts them.",
            "- Prefer diff-first continuation from the accepted checkpoint over reconstructing unchanged repository state.",
            "- If substantially the same diagnostic/search/transformation is performed twice, make it reusable before doing it a third time.",
            "- Expand to roadmap/architecture/full handoff documents only when the task crosses those boundaries or the packet is insufficient.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--focus", default="", help="Short task phrase used to select relevant context.")
    result.add_argument("--issue", type=int, help="Optional issue number to display in the packet.")
    result.add_argument("--base-ref", default="dev", help="Integration ref used for changed-path context.")
    result.add_argument("--output", type=Path, help="Optional local scratch file; stdout is the default.")
    result.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS)
    result.add_argument(
        "--check",
        action="store_true",
        help="Validate packet generation and the default size budget without printing the packet.",
    )
    return result


def main() -> int:
    args = parser().parse_args()
    if args.max_chars < 2_000:
        raise SystemExit("--max-chars must be at least 2000")
    repo_root = _repo_root()
    packet = build_packet(
        repo_root,
        focus=args.focus,
        issue=args.issue,
        base_ref=args.base_ref,
    )
    if len(packet) > args.max_chars:
        raise SystemExit(
            f"Generated packet is {len(packet)} characters; budget is {args.max_chars}. "
            "Tighten the selectors instead of increasing routine reset context."
        )
    if args.check:
        print(f"agent context check ok: {len(packet)} characters")
        return 0
    if args.output is not None:
        output = args.output if args.output.is_absolute() else repo_root / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(packet, encoding="utf-8")
        print(f"Wrote generated agent context: {output}")
        return 0
    print(packet, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
