"""Checkout containment and GitHub remote identity verification."""

from __future__ import annotations

import configparser
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from nerve_center.code_shop.domain import CodeShopProject

_SCP_GITHUB = re.compile(r"^(?:[^@]+@)?github\.com:(?P<path>[^/]+/[^/]+?)(?:\.git)?$")


class CheckoutValidationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class CheckoutVerification:
    canonical_path: str
    approved_root: str
    remote_identity: str
    detail: dict[str, object]


def verify_checkout(
    project: CodeShopProject,
    checkout_path: str | Path,
    approved_roots: tuple[Path, ...],
) -> CheckoutVerification:
    if not approved_roots:
        raise CheckoutValidationError("no Code Shop checkout roots are approved")
    path = Path(checkout_path).expanduser().resolve(strict=True)
    if not path.is_dir():
        raise CheckoutValidationError("checkout path is not a directory")
    root = _approved_root(path, approved_roots)
    config_path = path / ".git" / "config"
    if not config_path.is_file():
        raise CheckoutValidationError("checkout does not contain a .git/config file")
    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read(config_path, encoding="utf-8")
    except configparser.Error as error:
        raise CheckoutValidationError("checkout Git configuration is invalid") from error
    expected = project.full_name.lower()
    matches: list[tuple[str, str]] = []
    for section in parser.sections():
        if not section.startswith('remote "'):
            continue
        url = parser.get(section, "url", fallback="").strip()
        identity = normalize_github_remote(url)
        if identity == expected:
            remote_name = section.removeprefix('remote "').removesuffix('"')
            matches.append((remote_name, identity))
    if not matches:
        raise CheckoutValidationError(
            f"checkout Git remote does not match GitHub repository {project.full_name}"
        )
    remote_name, identity = matches[0]
    return CheckoutVerification(
        canonical_path=str(path),
        approved_root=str(root),
        remote_identity=identity,
        detail={"remote_name": remote_name, "repository": project.full_name},
    )


def normalize_github_remote(value: str) -> str | None:
    raw = value.strip()
    if not raw:
        return None
    scp = _SCP_GITHUB.fullmatch(raw)
    if scp:
        return _normalize_path(scp.group("path"))
    parsed = urlparse(raw)
    if parsed.hostname != "github.com":
        return None
    return _normalize_path(parsed.path.lstrip("/"))


def resolve_scoped_path(checkout_path: str, resource_path: str) -> Path:
    checkout = Path(checkout_path).resolve()
    candidate = Path(resource_path)
    resolved = (
        candidate.resolve()
        if candidate.is_absolute()
        else (checkout / candidate).resolve()
    )
    try:
        resolved.relative_to(checkout)
    except ValueError as error:
        raise CheckoutValidationError(
            f"resource path {resource_path!r} escapes the linked checkout"
        ) from error
    return resolved


def _approved_root(path: Path, roots: tuple[Path, ...]) -> Path:
    for configured in roots:
        root = configured.expanduser().resolve()
        try:
            path.relative_to(root)
            return root
        except ValueError:
            continue
    raise CheckoutValidationError("checkout path is outside manager-approved roots")


def _normalize_path(value: str) -> str | None:
    path = value.strip().strip("/")
    if path.endswith(".git"):
        path = path[:-4]
    parts = [part for part in path.split("/") if part]
    if len(parts) != 2:
        return None
    return f"{parts[0]}/{parts[1]}".lower()
