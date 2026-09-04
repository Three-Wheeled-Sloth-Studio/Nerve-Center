#!/usr/bin/env python3
"""Validate Nerve Center's Agent Academy-compatible refs harness."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit("PyYAML is required: python -m pip install pyyaml") from exc

try:
    from check_case_collisions import collision_groups, tracked_paths
    from generate_okf_indexes import expected_indexes
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Nerve Center refs tools are incomplete") from exc

ROOT = Path(__file__).resolve().parents[2]
REFS = ROOT / "refs"
POLICY = REFS / "templatePolicy.yaml"
PROFILE = REFS / "okfProfile.yaml"
REGISTRY = REFS / "schemas" / "schemaRegistry.yaml"
OKF_RESERVED = {"index.md", "log.md"}
OKF_STATUSES = {"draft", "stable", "deprecated"}
OKF_TIMESTAMP_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def ref_files() -> list[Path]:
    return [path for path in REFS.rglob("*") if path.is_file() and "__pycache__" not in path.parts]


def yaml_files() -> list[Path]:
    return [path for path in ref_files() if path.suffix.lower() in {".yaml", ".yml"}]


def markdown_files() -> list[Path]:
    return [path for path in ref_files() if path.suffix.lower() == ".md"]


def add_error(errors: list[str], path: Path | str, message: str) -> None:
    label = path if isinstance(path, str) else rel(path)
    errors.append(f"{label}: {message}")


def parse_frontmatter(path: Path, errors: list[str]) -> dict[str, Any] | None:
    contents = text(path)
    if not contents.startswith("---\n"):
        add_error(errors, path, "OKF concept is missing YAML frontmatter")
        return None
    end = contents.find("\n---\n", 4)
    if end < 0:
        add_error(errors, path, "OKF frontmatter is not closed")
        return None
    try:
        data = yaml.load(contents[4:end], Loader=yaml.BaseLoader) or {}
    except yaml.YAMLError as exc:
        add_error(errors, path, f"invalid OKF frontmatter: {exc}")
        return None
    if not isinstance(data, dict):
        add_error(errors, path, "OKF frontmatter must be a mapping")
        return None
    return data


def validate_timestamp(value: Any, path: Path, field: str, errors: list[str]) -> None:
    if not isinstance(value, str) or not OKF_TIMESTAMP_RE.fullmatch(value):
        add_error(errors, path, f"`{field}` must be ISO 8601 with an explicit UTC offset")


def validate_frontmatter(path: Path, data: dict[str, Any], errors: list[str]) -> None:
    concept_type = data.get("type")
    if not isinstance(concept_type, str) or not concept_type.strip():
        add_error(errors, path, "OKF frontmatter must contain a non-empty `type`")
    status = data.get("status")
    if status is not None and status not in OKF_STATUSES:
        add_error(errors, path, f"unsupported OKF status `{status}`")
    for field in ("stale_after",):
        if data.get(field) is not None:
            validate_timestamp(data[field], path, field, errors)
    generated = data.get("generated")
    if generated is not None:
        if not isinstance(generated, dict) or not generated.get("by"):
            add_error(errors, path, "`generated` must contain non-empty `by`")
        elif generated.get("at") is not None:
            validate_timestamp(generated["at"], path, "generated.at", errors)
    verified = data.get("verified")
    if verified is not None:
        records = verified if isinstance(verified, list) else [verified]
        for index, record in enumerate(records):
            if not isinstance(record, dict) or not record.get("by") or not record.get("at"):
                add_error(errors, path, f"`verified[{index}]` must contain `by` and `at`")
            else:
                validate_timestamp(record["at"], path, f"verified[{index}].at", errors)


def validate_required(policy: dict[str, Any], errors: list[str]) -> None:
    for item in policy.get("required_files", []):
        if not (ROOT / item).is_file():
            add_error(errors, item, "required file is missing")


def validate_yaml(errors: list[str]) -> dict[str, Any]:
    loaded: dict[str, Any] = {}
    for path in yaml_files():
        try:
            loaded[rel(path)] = load_yaml(path)
        except yaml.YAMLError as exc:
            add_error(errors, path, f"invalid YAML: {exc}")
    return loaded


def validate_schema_keys(loaded: dict[str, Any], errors: list[str]) -> None:
    registry = loaded.get(rel(REGISTRY)) or load_yaml(REGISTRY)
    defaults = registry.get("defaults", {}).get("yaml_required_top_level_keys", [])
    for path in yaml_files():
        data = loaded.get(rel(path), {})
        if not isinstance(data, dict):
            add_error(errors, path, "YAML root must be a mapping")
            continue
        for key in defaults:
            if key not in data:
                add_error(errors, path, f"missing required top-level key `{key}`")
        schema_ref = data.get("schema")
        if not isinstance(schema_ref, str):
            add_error(errors, path, "`schema` must be a relative path string")
        elif Path(schema_ref).is_absolute() or re.match(r"^[A-Za-z]:", schema_ref):
            add_error(errors, path, "`schema` must be relative")
        elif not (ROOT / schema_ref).is_file():
            add_error(errors, path, f"schema reference `{schema_ref}` does not exist")
    for item, schema in registry.get("schemas", {}).items():
        data = loaded.get(item)
        if data is None:
            continue
        for key in schema.get("required_top_level_keys", []):
            if key not in data:
                add_error(errors, item, f"missing schema top-level key `{key}`")


def validate_placeholders(policy: dict[str, Any], mode: str, errors: list[str]) -> None:
    if mode != "initialized":
        return
    bootstrap = {ROOT / item for item in policy.get("bootstrap_files", [])}
    token_re = re.compile(r"\b[A-Z][A-Z0-9_]*TODO[A-Z0-9_]*\b")
    for path in bootstrap:
        if path.is_file() and token_re.search(text(path)):
            add_error(errors, path, "bootstrap file contains a template TODO placeholder")


def validate_secret_scan(policy: dict[str, Any], errors: list[str]) -> None:
    patterns = policy.get("validation", {}).get("disallowed_secret_patterns", [])
    regexes = [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
    assignment_re = re.compile(r"[:=]\s*['\"]?[A-Za-z0-9_/\-+=]{16,}")
    for path in ref_files():
        for lineno, line in enumerate(text(path).splitlines(), start=1):
            if any(regex.search(line) for regex in regexes) and assignment_re.search(line):
                add_error(errors, path, f"possible secret-like value on line {lineno}")


def validate_portable_paths(errors: list[str]) -> None:
    absolute_windows = re.compile(r"[A-Za-z]:\\")
    absolute_unix = re.compile(r"(?<!:)\s/[A-Za-z0-9_.-]")
    for path in yaml_files():
        contents = text(path)
        if absolute_windows.search(contents):
            add_error(errors, path, "contains a Windows absolute path")
        if absolute_unix.search(contents):
            add_error(errors, path, "contains a Unix absolute path")


def validate_concepts(errors: list[str]) -> None:
    for path in markdown_files():
        if path.name in OKF_RESERVED:
            continue
        data = parse_frontmatter(path, errors)
        if data is not None:
            validate_frontmatter(path, data, errors)


def validate_profile(loaded: dict[str, Any], errors: list[str]) -> None:
    profile = loaded.get(rel(PROFILE))
    if not isinstance(profile, dict):
        add_error(errors, PROFILE, "OKF profile must be a mapping")
        return
    okf = profile.get("okf")
    bundle = profile.get("bundle")
    academy = profile.get("agent_academy")
    if not isinstance(okf, dict) or not okf.get("version"):
        add_error(errors, PROFILE, "missing `okf.version`")
        return
    if not isinstance(bundle, dict) or bundle.get("root") != "refs":
        add_error(errors, PROFILE, "`bundle.root` must be `refs`")
    baseline = okf.get("baseline_commit")
    if not isinstance(baseline, str) or not re.fullmatch(r"[0-9a-f]{40}", baseline):
        add_error(errors, PROFILE, "`okf.baseline_commit` must be a full commit SHA")
    source_baseline = academy.get("source_baseline") if isinstance(academy, dict) else None
    if not isinstance(source_baseline, str) or not re.fullmatch(r"[0-9a-f]{40}", source_baseline):
        add_error(errors, PROFILE, "`agent_academy.source_baseline` must be a full commit SHA")

    root_index = REFS / "index.md"
    if not root_index.is_file():
        add_error(errors, root_index, "OKF bundle root index is missing")
        return
    root_meta = parse_frontmatter(root_index, errors)
    if root_meta is not None:
        if set(root_meta) != {"okf_version"}:
            add_error(errors, root_index, "root index frontmatter may contain only `okf_version`")
        if root_meta.get("okf_version") != str(okf.get("version")):
            add_error(errors, root_index, "`okf_version` does not match refs/okfProfile.yaml")
    for path in REFS.rglob("index.md"):
        if path != root_index and text(path).startswith("---\n"):
            add_error(errors, path, "non-root OKF indexes must not contain frontmatter")


def validate_indexes(errors: list[str]) -> None:
    try:
        expected = expected_indexes()
    except SystemExit as exc:
        add_error(errors, "refs/index.md", f"could not generate OKF indexes: {exc}")
        return
    expected_paths = set(expected)
    existing_paths = {path for path in REFS.rglob("index.md") if "__pycache__" not in path.parts}
    for path, wanted in expected.items():
        if not path.is_file():
            add_error(errors, path, "generated OKF index is missing")
        elif text(path) != wanted:
            add_error(errors, path, "generated OKF index is stale")
    for path in existing_paths - expected_paths:
        add_error(errors, path, "unexpected generated OKF index")


def validate_case_collisions(errors: list[str]) -> None:
    try:
        groups = collision_groups(tracked_paths())
    except Exception as exc:  # noqa: BLE001 - report environment failure as validation failure
        add_error(errors, "git index", f"could not check tracked-path casing: {exc}")
        return
    for group in groups:
        add_error(errors, "git index", f"case-colliding tracked paths: {' | '.join(group)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["template", "initialized"], default="initialized")
    args = parser.parse_args()
    errors: list[str] = []
    if not POLICY.is_file():
        add_error(errors, POLICY, "template policy is missing")
        print("\n".join(errors), file=sys.stderr)
        return 1

    policy = load_yaml(POLICY)
    validate_required(policy, errors)
    loaded = validate_yaml(errors)
    validate_schema_keys(loaded, errors)
    validate_placeholders(policy, args.mode, errors)
    validate_secret_scan(policy, errors)
    validate_portable_paths(errors)
    validate_concepts(errors)
    validate_profile(loaded, errors)
    validate_indexes(errors)
    validate_case_collisions(errors)

    if errors:
        print("refs validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(f"refs validation passed ({args.mode} mode, Agent Academy OKF-compatible)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
