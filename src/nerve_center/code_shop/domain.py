"""Shared Code Shop domain contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class ProjectLifecycle(StrEnum):
    ENABLED = "enabled"
    PAUSED = "paused"
    OBSERVE_ONLY = "observe_only"
    NEEDS_ATTENTION = "needs_attention"
    EXCLUDED = "excluded"


class ActionPolicy(StrEnum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


class EffectiveDecision(StrEnum):
    EXECUTE = "execute"
    REQUEST_ATTENTION = "request_attention"
    DENY = "deny"


class EngineeringCapability(StrEnum):
    ARCHITECTURE_PLANNING = "architecture_planning"
    TASK_DECOMPOSITION = "task_decomposition"
    CODE_IMPLEMENTATION = "code_implementation"
    DEBUGGING = "debugging"
    CODE_REVIEW = "code_review"
    RESEARCH = "research"


class ExecutionCapability(StrEnum):
    REPO_READ = "repo.read"
    REPO_WRITE = "repo.write"
    GIT_BRANCH = "git.branch"
    GIT_COMMIT = "git.commit"
    GIT_PUSH = "git.push"
    GIT_INTEGRATION_MERGE = "git.integration_merge"
    SHELL_EXECUTE = "shell.execute"
    TEST_EXECUTE = "test.execute"
    GITHUB_REPO_READ = "github.repo.read"
    GITHUB_ISSUE_READ = "github.issue.read"
    GITHUB_ISSUE_WRITE = "github.issue.write"
    GITHUB_PR_READ = "github.pr.read"
    GITHUB_PR_WRITE = "github.pr.write"
    GITHUB_WORKFLOW_TRIGGER = "github.workflow.trigger"
    RUNNER_EXECUTE = "runner.execute"
    WEB_READ = "web.read"


class ProjectAction(StrEnum):
    CHECKOUT_READ = "checkout_read"
    CHECKOUT_WRITE = "checkout_write"
    BRANCH_CREATE = "branch_create"
    COMMIT = "commit"
    PUSH = "push"
    GITHUB_REPO_READ = "github_repo_read"
    ISSUE_READ = "issue_read"
    ISSUE_MUTATION = "issue_mutation"
    PR_READ = "pr_read"
    PR_MUTATION = "pr_mutation"
    INTEGRATION_MERGE = "integration_merge"
    RELEASE_PROMOTION = "release_promotion"
    TEST_EXECUTION = "test_execution"
    WEB_READ = "web_read"
    WORKFLOW_TRIGGER = "workflow_trigger"
    HOSTED_RUNNER_EXECUTION = "hosted_runner_execution"
    DEPENDENCY_MODIFICATION = "dependency_modification"
    CI_WORKFLOW_MODIFICATION = "ci_workflow_modification"
    DEPLOYMENT = "deployment"
    CREDENTIAL_MUTATION = "credential_mutation"
    DESTRUCTIVE_GIT = "destructive_git"
    IRREVERSIBLE_DATA_CHANGE = "irreversible_data_change"


class EngineeringTaskState(StrEnum):
    QUEUED = "queued"
    PLANNING = "planning"
    IN_PROGRESS = "in_progress"
    VALIDATING = "validating"
    WAITING_ON_CI = "waiting_on_ci"
    WAITING_ON_RUNNER = "waiting_on_runner"
    WAITING_ON_EXTERNAL_DEPENDENCY = "waiting_on_external_dependency"
    NEEDS_USER_INPUT = "needs_user_input"
    ESCALATION_RECOMMENDED = "escalation_recommended"
    COMPLETED = "completed"
    FAILED_OR_ABANDONED = "failed_or_abandoned"


@dataclass(frozen=True, slots=True)
class GitHubRepositoryIdentity:
    repository_id: str
    full_name: str
    visibility: str
    default_branch: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CodeShopProject:
    repository_id: str
    full_name: str
    visibility: str
    default_branch: str
    lifecycle: ProjectLifecycle
    priority: int
    branch_policy: dict[str, Any]
    metadata: dict[str, Any]
    hosted_runner_eligible: bool
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class CheckoutLink:
    repository_id: str
    canonical_path: str
    approved_root: str
    remote_identity: str
    verified: bool
    verification_detail: dict[str, Any]
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class AuthorityPolicyEnvelope:
    repository_id: str
    action: ProjectAction
    policy: ActionPolicy
    scope: dict[str, Any]
    provenance: dict[str, Any]
    version: int
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class EngineeringTask:
    id: str
    repository_id: str
    title: str
    capability: EngineeringCapability
    state: EngineeringTaskState
    source_backlog: dict[str, Any]
    blocker: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class EngineeringAttempt:
    id: str
    task_id: str
    number: int
    status: str
    approach: str
    context_inputs: dict[str, Any]
    manager_provenance: dict[str, Any]
    touched_files: tuple[str, ...]
    command_summaries: tuple[str, ...]
    resources: dict[str, Any]
    outcome: dict[str, Any]
    created_at: datetime
    finished_at: datetime | None


@dataclass(frozen=True, slots=True)
class AuthorityDecision:
    id: str
    task_id: str
    repository_id: str
    module_id: str
    action: ProjectAction
    capability: ExecutionCapability
    effective_decision: EffectiveDecision
    risk_findings: tuple[str, ...]
    reason: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class Escalation:
    id: str
    task_id: str
    reason: str
    evidence: dict[str, Any]
    failed_invariant: str
    recommended_capability: str
    compact_handoff: str
    dispositions: tuple[str, ...]
    status: str
    created_at: datetime
    resolved_at: datetime | None


@dataclass(frozen=True, slots=True)
class OutcomeEvidence:
    id: str
    task_id: str
    attempt_id: str | None
    kind: str
    payload: dict[str, Any]
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ModuleTrustProvenance:
    module_id: str
    official: bool
    source: str


@dataclass(frozen=True, slots=True)
class ExecutionRequest:
    module_id: str
    task_id: str
    repository_id: str
    action: ProjectAction
    capability: ExecutionCapability
    arguments: dict[str, Any]
    expected_outputs: dict[str, Any]
    timeout_seconds: int
    resource_limits: dict[str, Any]
    idempotency_key: str
    branch: str | None = None
    resource_paths: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AuthorityEvaluation:
    effective_decision: EffectiveDecision
    risk_findings: tuple[str, ...]
    reason: str


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    status: str
    capability: ExecutionCapability
    idempotency_key: str
    output: dict[str, Any]
