"""Manager-owned GitHub repository discovery contract for Code Shop."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from nerve_center.code_shop.domain import GitHubRepositoryIdentity


class GitHubRepositoryConnector(Protocol):
    def list_repositories(self) -> list[GitHubRepositoryIdentity]: ...


class EmptyGitHubRepositoryConnector:
    """Safe production default until an authenticated connector is configured."""

    def list_repositories(self) -> list[GitHubRepositoryIdentity]:
        return []


class StaticGitHubRepositoryConnector:
    """Deterministic connector used by tests and local contract validation."""

    def __init__(self, repositories: Iterable[GitHubRepositoryIdentity]) -> None:
        self._repositories = tuple(repositories)

    def list_repositories(self) -> list[GitHubRepositoryIdentity]:
        return list(self._repositories)
