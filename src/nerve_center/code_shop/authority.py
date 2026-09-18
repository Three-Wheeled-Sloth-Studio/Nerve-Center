"""Pure manager-owned Code Shop authority and risk evaluation."""

from __future__ import annotations

from nerve_center.code_shop.checkout import CheckoutValidationError, resolve_scoped_path
from nerve_center.code_shop.domain import (
    ActionPolicy,
    AuthorityEvaluation,
    AuthorityPolicyEnvelope,
    CheckoutLink,
    CodeShopProject,
    EffectiveDecision,
    EngineeringTask,
    ExecutionCapability,
    ExecutionRequest,
    ModuleTrustProvenance,
    ProjectAction,
    ProjectLifecycle,
)

_DECLARED_CAPABILITIES = frozenset(ExecutionCapability)

_ACTION_CAPABILITY: dict[ProjectAction, ExecutionCapability] = {
    ProjectAction.CHECKOUT_READ: ExecutionCapability.REPO_READ,
    ProjectAction.CHECKOUT_WRITE: ExecutionCapability.REPO_WRITE,
    ProjectAction.BRANCH_CREATE: ExecutionCapability.GIT_BRANCH,
    ProjectAction.COMMIT: ExecutionCapability.GIT_COMMIT,
    ProjectAction.PUSH: ExecutionCapability.GIT_PUSH,
    ProjectAction.GITHUB_REPO_READ: ExecutionCapability.GITHUB_REPO_READ,
    ProjectAction.ISSUE_READ: ExecutionCapability.GITHUB_ISSUE_READ,
    ProjectAction.ISSUE_MUTATION: ExecutionCapability.GITHUB_ISSUE_WRITE,
    ProjectAction.PR_READ: ExecutionCapability.GITHUB_PR_READ,
    ProjectAction.PR_MUTATION: ExecutionCapability.GITHUB_PR_WRITE,
    ProjectAction.INTEGRATION_MERGE: ExecutionCapability.GIT_INTEGRATION_MERGE,
    ProjectAction.RELEASE_PROMOTION: ExecutionCapability.GIT_PUSH,
    ProjectAction.TEST_EXECUTION: ExecutionCapability.TEST_EXECUTE,
    ProjectAction.WEB_READ: ExecutionCapability.WEB_READ,
    ProjectAction.WORKFLOW_TRIGGER: ExecutionCapability.GITHUB_WORKFLOW_TRIGGER,
    ProjectAction.HOSTED_RUNNER_EXECUTION: ExecutionCapability.RUNNER_EXECUTE,
    ProjectAction.DEPENDENCY_MODIFICATION: ExecutionCapability.REPO_WRITE,
    ProjectAction.CI_WORKFLOW_MODIFICATION: ExecutionCapability.REPO_WRITE,
    ProjectAction.DEPLOYMENT: ExecutionCapability.SHELL_EXECUTE,
    ProjectAction.CREDENTIAL_MUTATION: ExecutionCapability.SHELL_EXECUTE,
    ProjectAction.DESTRUCTIVE_GIT: ExecutionCapability.SHELL_EXECUTE,
    ProjectAction.IRREVERSIBLE_DATA_CHANGE: ExecutionCapability.SHELL_EXECUTE,
}

_INSPECTION_ACTIONS = frozenset(
    {
        ProjectAction.CHECKOUT_READ,
        ProjectAction.GITHUB_REPO_READ,
        ProjectAction.ISSUE_READ,
        ProjectAction.PR_READ,
        ProjectAction.WEB_READ,
    }
)

_BRANCH_SCOPED_ACTIONS = frozenset(
    {
        ProjectAction.BRANCH_CREATE,
        ProjectAction.COMMIT,
        ProjectAction.PUSH,
        ProjectAction.INTEGRATION_MERGE,
        ProjectAction.RELEASE_PROMOTION,
        ProjectAction.CI_WORKFLOW_MODIFICATION,
    }
)

_ATTENTION_ACTIONS = frozenset(
    {
        ProjectAction.RELEASE_PROMOTION,
        ProjectAction.HOSTED_RUNNER_EXECUTION,
        ProjectAction.CI_WORKFLOW_MODIFICATION,
        ProjectAction.DEPLOYMENT,
        ProjectAction.CREDENTIAL_MUTATION,
        ProjectAction.IRREVERSIBLE_DATA_CHANGE,
    }
)

_PROHIBITED_ACTIONS = frozenset({ProjectAction.DESTRUCTIVE_GIT})


class AuthorityEvaluator:
    def evaluate(
        self,
        *,
        project: CodeShopProject,
        checkout: CheckoutLink | None,
        task: EngineeringTask | None,
        policy: AuthorityPolicyEnvelope | None,
        trust: ModuleTrustProvenance,
        request: ExecutionRequest,
    ) -> AuthorityEvaluation:
        if not trust.official or trust.source != "builtin_registry":
            return _deny("requesting module is not manager-trusted as an official module")
        if request.capability not in _DECLARED_CAPABILITIES:
            return _deny("requested execution capability is not manager-declared")
        expected_capability = _ACTION_CAPABILITY.get(request.action)
        if expected_capability != request.capability:
            return _deny(
                f"action {request.action.value} requires capability "
                f"{expected_capability.value if expected_capability else 'none'}"
            )
        if task is None or task.id != request.task_id:
            return _deny("execution is not attributable to a durable Code Shop task")
        if task.repository_id != project.repository_id:
            return _deny("task repository does not match the requested project")
        if project.lifecycle in {ProjectLifecycle.PAUSED, ProjectLifecycle.EXCLUDED}:
            return _deny(f"project lifecycle {project.lifecycle.value} blocks execution")
        if project.lifecycle == ProjectLifecycle.NEEDS_ATTENTION:
            return _attention("project requires human attention before execution")
        if (
            project.lifecycle == ProjectLifecycle.OBSERVE_ONLY
            and request.action not in _INSPECTION_ACTIONS
        ):
            return _deny("observe-only projects cannot mutate local or GitHub state")
        if checkout is None or not checkout.verified:
            return _deny("project has no verified linked checkout")
        if policy is None:
            return _attention("project action has no explicit user policy")
        if policy.policy == ActionPolicy.DENY:
            return _deny("project action policy denies this action")
        if policy.policy == ActionPolicy.ASK:
            return _attention("project action policy requires human approval")
        if request.action in _PROHIBITED_ACTIONS:
            return AuthorityEvaluation(
                EffectiveDecision.DENY,
                ("prohibited_high_risk_action",),
                "destructive Git operations are never silently authorized",
            )
        if request.action in _ATTENTION_ACTIONS:
            return AuthorityEvaluation(
                EffectiveDecision.REQUEST_ATTENTION,
                ("attention_required_high_risk_action",),
                "manager risk policy requires explicit human handling",
            )
        branch_evaluation = self._branch_scope(project, request)
        if branch_evaluation is not None:
            return branch_evaluation
        try:
            for resource_path in request.resource_paths:
                resolve_scoped_path(checkout.canonical_path, resource_path)
        except CheckoutValidationError as error:
            return _deny(str(error))
        return AuthorityEvaluation(
            EffectiveDecision.EXECUTE,
            (),
            "trusted module, explicit allow policy, verified scope, and acceptable risk",
        )

    @staticmethod
    def _branch_scope(
        project: CodeShopProject,
        request: ExecutionRequest,
    ) -> AuthorityEvaluation | None:
        if request.action not in _BRANCH_SCOPED_ACTIONS:
            return None
        if not request.branch:
            return _deny("branch-scoped actions require an explicit branch")
        branch_policy = project.branch_policy or {}
        protected = {str(item) for item in branch_policy.get("protected_branches", [])}
        if request.branch in protected:
            return AuthorityEvaluation(
                EffectiveDecision.REQUEST_ATTENTION,
                ("protected_branch",),
                f"branch {request.branch!r} requires human handling",
            )
        allowed = {str(item) for item in branch_policy.get("allowed_branches", [])}
        if allowed and request.branch not in allowed:
            return _deny(f"branch {request.branch!r} is outside the project branch policy")
        return None


def _deny(reason: str) -> AuthorityEvaluation:
    return AuthorityEvaluation(EffectiveDecision.DENY, (), reason)


def _attention(reason: str) -> AuthorityEvaluation:
    return AuthorityEvaluation(EffectiveDecision.REQUEST_ATTENTION, (), reason)
