"""Manager-owned Code Shop orchestration service."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from nerve_center.attention.domain import AttentionKind
from nerve_center.attention.service import AttentionService
from nerve_center.code_shop.authority import AuthorityEvaluator
from nerve_center.code_shop.checkout import verify_checkout
from nerve_center.code_shop.domain import (
    ActionPolicy,
    AuthorityDecision,
    AuthorityPolicyEnvelope,
    CheckoutLink,
    CodeShopProject,
    EffectiveDecision,
    EngineeringAttempt,
    EngineeringCapability,
    EngineeringTask,
    EngineeringTaskState,
    Escalation,
    ExecutionRequest,
    ExecutionResult,
    GitHubRepositoryIdentity,
    ModuleTrustProvenance,
    OutcomeEvidence,
    ProjectAction,
    ProjectLifecycle,
)
from nerve_center.code_shop.execution import DeterministicExecutionHost, ExecutionHost
from nerve_center.code_shop.github import GitHubRepositoryConnector
from nerve_center.persistence.code_shop import CodeShopRepository


class AuthorityNotGrantedError(RuntimeError):
    pass


class CodeShopService:
    def __init__(
        self,
        repository: CodeShopRepository,
        connector: GitHubRepositoryConnector,
        approved_checkout_roots: tuple[Path, ...],
        *,
        execution_host: ExecutionHost | None = None,
        official_module_ids: tuple[str, ...] = ("code_shop",),
        attention: AttentionService | None = None,
    ) -> None:
        self.repository = repository
        self.connector = connector
        self.approved_checkout_roots = tuple(approved_checkout_roots)
        self.execution_host = execution_host or DeterministicExecutionHost()
        self.official_module_ids = frozenset(official_module_ids)
        self.authority = AuthorityEvaluator()
        self.attention = attention

    def trust_provenance(self, module_id: str) -> ModuleTrustProvenance:
        return ModuleTrustProvenance(
            module_id=module_id,
            official=module_id in self.official_module_ids,
            source="builtin_registry" if module_id in self.official_module_ids else "untrusted",
        )

    def discover_repositories(self) -> list[GitHubRepositoryIdentity]:
        return self.connector.list_repositories()

    def select_repository(self, repository_id: str) -> CodeShopProject:
        matches = [
            item
            for item in self.connector.list_repositories()
            if item.repository_id == repository_id
        ]
        if not matches:
            raise KeyError(f"GitHub repository {repository_id!r} is not discoverable")
        return self.repository.upsert_project(matches[0])

    def synchronize_projects(self) -> list[CodeShopProject]:
        discovered = {
            item.repository_id: item for item in self.connector.list_repositories()
        }
        for project in self.repository.list_projects():
            current = discovered.get(project.repository_id)
            if current is not None:
                self.repository.upsert_project(current)
        return self.repository.list_projects()

    def list_projects(self) -> list[CodeShopProject]:
        return self.repository.list_projects()

    def configure_project(
        self,
        repository_id: str,
        *,
        lifecycle: ProjectLifecycle | None = None,
        priority: int | None = None,
        branch_policy: dict[str, Any] | None = None,
        hosted_runner_eligible: bool | None = None,
    ) -> CodeShopProject:
        return self.repository.update_project(
            repository_id,
            lifecycle=lifecycle,
            priority=priority,
            branch_policy=branch_policy,
            hosted_runner_eligible=hosted_runner_eligible,
        )

    def link_checkout(self, repository_id: str, path: str) -> CheckoutLink:
        project = self.repository.get_project(repository_id)
        verified = verify_checkout(project, path, self.approved_checkout_roots)
        return self.repository.set_checkout(
            repository_id,
            canonical_path=verified.canonical_path,
            approved_root=verified.approved_root,
            remote_identity=verified.remote_identity,
            verified=True,
            verification_detail=verified.detail,
        )

    def unlink_checkout(self, repository_id: str) -> None:
        self.repository.get_project(repository_id)
        self.repository.remove_checkout(repository_id)

    def checkout(self, repository_id: str) -> CheckoutLink | None:
        self.repository.get_project(repository_id)
        return self.repository.get_checkout(repository_id)

    def set_policy(
        self,
        repository_id: str,
        action: ProjectAction,
        policy: ActionPolicy,
        *,
        scope: dict[str, Any] | None = None,
        provenance: dict[str, Any] | None = None,
    ) -> AuthorityPolicyEnvelope:
        return self.repository.set_policy(
            repository_id,
            action,
            policy,
            scope=dict(scope or {}),
            provenance=dict(provenance or {}),
        )

    def policies(self, repository_id: str) -> list[AuthorityPolicyEnvelope]:
        self.repository.get_project(repository_id)
        return self.repository.list_policies(repository_id)

    def create_task(
        self,
        repository_id: str,
        *,
        title: str,
        capability: EngineeringCapability,
        source_backlog: dict[str, Any] | None = None,
    ) -> EngineeringTask:
        return self.repository.create_task(
            repository_id,
            title=title.strip(),
            capability=capability,
            source_backlog=dict(source_backlog or {}),
        )

    def list_tasks(
        self, repository_id: str | None = None, limit: int = 200
    ) -> list[EngineeringTask]:
        return self.repository.list_tasks(repository_id, limit)

    def record_attempt(
        self,
        task_id: str,
        *,
        status: str,
        approach: str,
        context_inputs: dict[str, Any] | None = None,
        manager_provenance: dict[str, Any] | None = None,
        touched_files: tuple[str, ...] = (),
        command_summaries: tuple[str, ...] = (),
        resources: dict[str, Any] | None = None,
        outcome: dict[str, Any] | None = None,
        max_failed_attempts: int = 3,
    ) -> tuple[EngineeringAttempt, Escalation | None]:
        if max_failed_attempts < 1:
            raise ValueError("max_failed_attempts must be positive")
        attempt = self.repository.record_attempt(
            task_id,
            status=status,
            approach=approach,
            context_inputs=dict(context_inputs or {}),
            manager_provenance=dict(manager_provenance or {}),
            touched_files=touched_files,
            command_summaries=command_summaries,
            resources=dict(resources or {}),
            outcome=dict(outcome or {}),
        )
        escalation: Escalation | None = None
        if status == "failed":
            failed = self.repository.failed_attempt_count(task_id)
            if (
                failed >= max_failed_attempts
                and not self.repository.has_open_escalation(task_id)
            ):
                task = self.repository.get_task(task_id)
                escalation = self.raise_escalation(
                    task_id,
                    reason="bounded_attempt_limit_reached",
                    evidence={"failed_attempts": failed, "last_attempt_id": attempt.id},
                    failed_invariant="engineering_attempt_budget",
                    recommended_capability=task.capability.value,
                    compact_handoff=(
                        f"Task {task.id} reached {failed} failed attempts. Review the "
                        "recorded approaches and decide whether to change capability, scope, "
                        "or stop the task."
                    ),
                )
        return attempt, escalation

    def record_outcome(
        self,
        task_id: str,
        *,
        attempt_id: str | None,
        kind: str,
        payload: dict[str, Any],
    ) -> OutcomeEvidence:
        return self.repository.record_outcome(
            task_id,
            attempt_id=attempt_id,
            kind=kind,
            payload=payload,
        )

    def raise_escalation(
        self,
        task_id: str,
        *,
        reason: str,
        evidence: dict[str, Any],
        failed_invariant: str,
        recommended_capability: str,
        compact_handoff: str,
        dispositions: tuple[str, ...] = (
            "retry_with_same_scope",
            "change_scope_or_capability",
            "stop_task",
        ),
    ) -> Escalation:
        task = self.repository.get_task(task_id)
        escalation = self.repository.create_escalation(
            task_id,
            reason=reason,
            evidence=evidence,
            failed_invariant=failed_invariant,
            recommended_capability=recommended_capability,
            compact_handoff=compact_handoff,
            dispositions=dispositions,
        )
        self.repository.set_task_state(
            task_id,
            EngineeringTaskState.ESCALATION_RECOMMENDED,
            blocker=reason,
        )
        if self.attention is not None:
            self.attention.submit(
                kind=AttentionKind.ATTENTION,
                module_id="code_shop",
                source_type="code_shop_escalation",
                source_id=escalation.id,
                idempotency_key=f"escalation:{escalation.id}",
                title=f"Code Shop task needs attention: {task.title}",
                summary=compact_handoff,
                context={
                    "task_id": task_id,
                    "repository_id": task.repository_id,
                    "reason": reason,
                    "evidence": dict(evidence),
                    "failed_invariant": failed_invariant,
                    "recommended_capability": recommended_capability,
                },
                allowed_dispositions=dispositions,
                validation={"source": "code_shop_escalation"},
                downstream_meaning={
                    "resolved_dependency": f"code_shop:task:{task_id}"
                },
                dependency_keys=(f"code_shop:task:{task_id}",),
            )
        return escalation

    def list_escalations(
        self, task_id: str | None = None, limit: int = 200
    ) -> list[Escalation]:
        return self.repository.list_escalations(task_id, limit)

    def evaluate(self, request: ExecutionRequest) -> AuthorityDecision:
        project = self.repository.get_project(request.repository_id)
        checkout = self.repository.get_checkout(request.repository_id)
        task = self._optional_task(request.task_id)
        policy = self.repository.get_policy(request.repository_id, request.action)
        trust = self.trust_provenance(request.module_id)
        evaluation = self.authority.evaluate(
            project=project,
            checkout=checkout,
            task=task,
            policy=policy,
            trust=trust,
            request=request,
        )
        decision = self.repository.record_decision(
            task_id=request.task_id,
            repository_id=request.repository_id,
            module_id=request.module_id,
            action=request.action,
            capability=request.capability,
            effective_decision=evaluation.effective_decision,
            risk_findings=evaluation.risk_findings,
            reason=evaluation.reason,
        )
        if evaluation.effective_decision == EffectiveDecision.REQUEST_ATTENTION:
            self.repository.update_project(
                request.repository_id,
                lifecycle=ProjectLifecycle.NEEDS_ATTENTION,
            )
        return decision

    def execute(
        self, request: ExecutionRequest
    ) -> tuple[AuthorityDecision, ExecutionResult]:
        decision = self.evaluate(request)
        if decision.effective_decision != EffectiveDecision.EXECUTE:
            raise AuthorityNotGrantedError(decision.reason)
        checkout = self.repository.get_checkout(request.repository_id)
        if checkout is None:
            raise AuthorityNotGrantedError("verified checkout disappeared before execution")
        result = self.execution_host.execute(request, checkout)
        self.repository.record_outcome(
            request.task_id,
            attempt_id=None,
            kind="execution_host",
            payload={
                "decision_id": decision.id,
                "status": result.status,
                "capability": result.capability.value,
                "idempotency_key": result.idempotency_key,
                "output": result.output,
            },
        )
        return decision, result

    def overview(self) -> dict[str, Any]:
        return {
            "module_trust": asdict(self.trust_provenance("code_shop")),
            "projects": [asdict(item) for item in self.repository.list_projects()],
            "tasks": [asdict(item) for item in self.repository.list_tasks(limit=50)],
            "escalations": [
                asdict(item) for item in self.repository.list_escalations(limit=50)
            ],
        }

    def _optional_task(self, task_id: str) -> EngineeringTask | None:
        try:
            return self.repository.get_task(task_id)
        except KeyError:
            return None
