"""Durable manager-owned Code Shop registry, authority, and work evidence."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    select,
)
from sqlalchemy.orm import Mapped, mapped_column

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
    ExecutionCapability,
    GitHubRepositoryIdentity,
    OutcomeEvidence,
    ProjectAction,
    ProjectLifecycle,
)
from nerve_center.persistence.database import Database
from nerve_center.persistence.models import Base


class CodeShopProjectModel(Base):
    __tablename__ = "code_shop_projects"

    repository_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    full_name: Mapped[str] = mapped_column(String(300), index=True)
    visibility: Mapped[str] = mapped_column(String(32))
    default_branch: Mapped[str] = mapped_column(String(255))
    lifecycle: Mapped[str] = mapped_column(String(32), index=True)
    priority: Mapped[int] = mapped_column(Integer, default=50)
    branch_policy: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    repository_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    hosted_runner_eligible: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CodeShopCheckoutModel(Base):
    __tablename__ = "code_shop_checkouts"

    repository_id: Mapped[str] = mapped_column(
        ForeignKey("code_shop_projects.repository_id"), primary_key=True
    )
    canonical_path: Mapped[str] = mapped_column(Text)
    approved_root: Mapped[str] = mapped_column(Text)
    remote_identity: Mapped[str] = mapped_column(String(300))
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verification_detail: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CodeShopAuthorityPolicyModel(Base):
    __tablename__ = "code_shop_authority_policies"
    __table_args__ = (
        UniqueConstraint("repository_id", "action", name="uq_code_shop_project_action"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    repository_id: Mapped[str] = mapped_column(
        ForeignKey("code_shop_projects.repository_id"), index=True
    )
    action: Mapped[str] = mapped_column(String(64), index=True)
    policy: Mapped[str] = mapped_column(String(16))
    scope: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CodeShopTaskModel(Base):
    __tablename__ = "code_shop_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    repository_id: Mapped[str] = mapped_column(
        ForeignKey("code_shop_projects.repository_id"), index=True
    )
    title: Mapped[str] = mapped_column(String(500))
    capability: Mapped[str] = mapped_column(String(64), index=True)
    state: Mapped[str] = mapped_column(String(64), index=True)
    source_backlog: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    blocker: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CodeShopAttemptModel(Base):
    __tablename__ = "code_shop_attempts"
    __table_args__ = (
        UniqueConstraint("task_id", "number", name="uq_code_shop_task_attempt_number"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("code_shop_tasks.id"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), index=True)
    approach: Mapped[str] = mapped_column(Text)
    context_inputs: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    manager_provenance: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    touched_files: Mapped[list[str]] = mapped_column(JSON, default=list)
    command_summaries: Mapped[list[str]] = mapped_column(JSON, default=list)
    resources: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    outcome: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CodeShopAuthorityDecisionModel(Base):
    __tablename__ = "code_shop_authority_decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(100), index=True)
    repository_id: Mapped[str] = mapped_column(
        ForeignKey("code_shop_projects.repository_id"), index=True
    )
    module_id: Mapped[str] = mapped_column(String(100), index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    capability: Mapped[str] = mapped_column(String(64))
    effective_decision: Mapped[str] = mapped_column(String(32), index=True)
    risk_findings: Mapped[list[str]] = mapped_column(JSON, default=list)
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class CodeShopEscalationModel(Base):
    __tablename__ = "code_shop_escalations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("code_shop_tasks.id"), index=True)
    reason: Mapped[str] = mapped_column(Text)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    failed_invariant: Mapped[str] = mapped_column(String(200))
    recommended_capability: Mapped[str] = mapped_column(String(100))
    compact_handoff: Mapped[str] = mapped_column(Text)
    dispositions: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(32), default="open", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CodeShopOutcomeEvidenceModel(Base):
    __tablename__ = "code_shop_outcome_evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("code_shop_tasks.id"), index=True)
    attempt_id: Mapped[str | None] = mapped_column(
        ForeignKey("code_shop_attempts.id"), nullable=True, index=True
    )
    kind: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class CodeShopRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def upsert_project(self, identity: GitHubRepositoryIdentity) -> CodeShopProject:
        now = datetime.now(UTC)
        with self.database.session() as session:
            model = session.get(CodeShopProjectModel, identity.repository_id)
            if model is None:
                model = CodeShopProjectModel(
                    repository_id=identity.repository_id,
                    full_name=identity.full_name,
                    visibility=identity.visibility,
                    default_branch=identity.default_branch,
                    lifecycle=ProjectLifecycle.PAUSED,
                    priority=50,
                    branch_policy={},
                    repository_metadata=dict(identity.metadata),
                    hosted_runner_eligible=False,
                    created_at=now,
                    updated_at=now,
                )
                session.add(model)
            else:
                model.full_name = identity.full_name
                model.visibility = identity.visibility
                model.default_branch = identity.default_branch
                model.repository_metadata = dict(identity.metadata)
                model.updated_at = now
            session.flush()
            return _project(model)

    def list_projects(self) -> list[CodeShopProject]:
        with self.database.session() as session:
            models = session.scalars(
                select(CodeShopProjectModel).order_by(CodeShopProjectModel.priority.desc())
            ).all()
            return [_project(item) for item in models]

    def get_project(self, repository_id: str) -> CodeShopProject:
        with self.database.session() as session:
            model = session.get(CodeShopProjectModel, repository_id)
            if model is None:
                raise KeyError(f"Code Shop project {repository_id!r} was not found")
            return _project(model)

    def update_project(
        self,
        repository_id: str,
        *,
        lifecycle: ProjectLifecycle | None = None,
        priority: int | None = None,
        branch_policy: dict[str, Any] | None = None,
        hosted_runner_eligible: bool | None = None,
    ) -> CodeShopProject:
        with self.database.session() as session:
            model = session.get(CodeShopProjectModel, repository_id)
            if model is None:
                raise KeyError(f"Code Shop project {repository_id!r} was not found")
            if lifecycle is not None:
                model.lifecycle = lifecycle
            if priority is not None:
                model.priority = priority
            if branch_policy is not None:
                model.branch_policy = dict(branch_policy)
            if hosted_runner_eligible is not None:
                model.hosted_runner_eligible = hosted_runner_eligible
            model.updated_at = datetime.now(UTC)
            session.flush()
            return _project(model)

    def set_checkout(
        self,
        repository_id: str,
        *,
        canonical_path: str,
        approved_root: str,
        remote_identity: str,
        verified: bool,
        verification_detail: dict[str, Any],
    ) -> CheckoutLink:
        self.get_project(repository_id)
        with self.database.session() as session:
            model = session.get(CodeShopCheckoutModel, repository_id)
            if model is None:
                model = CodeShopCheckoutModel(repository_id=repository_id)
                session.add(model)
            model.canonical_path = canonical_path
            model.approved_root = approved_root
            model.remote_identity = remote_identity
            model.verified = verified
            model.verification_detail = dict(verification_detail)
            model.updated_at = datetime.now(UTC)
            session.flush()
            return _checkout(model)

    def get_checkout(self, repository_id: str) -> CheckoutLink | None:
        with self.database.session() as session:
            model = session.get(CodeShopCheckoutModel, repository_id)
            return _checkout(model) if model is not None else None

    def remove_checkout(self, repository_id: str) -> None:
        with self.database.session() as session:
            model = session.get(CodeShopCheckoutModel, repository_id)
            if model is not None:
                session.delete(model)

    def set_policy(
        self,
        repository_id: str,
        action: ProjectAction,
        policy: ActionPolicy,
        *,
        scope: dict[str, Any],
        provenance: dict[str, Any],
    ) -> AuthorityPolicyEnvelope:
        self.get_project(repository_id)
        now = datetime.now(UTC)
        with self.database.session() as session:
            model = session.scalar(
                select(CodeShopAuthorityPolicyModel).where(
                    CodeShopAuthorityPolicyModel.repository_id == repository_id,
                    CodeShopAuthorityPolicyModel.action == action.value,
                )
            )
            if model is None:
                model = CodeShopAuthorityPolicyModel(
                    id=str(uuid4()),
                    repository_id=repository_id,
                    action=action.value,
                    version=1,
                )
                session.add(model)
            else:
                model.version += 1
            model.policy = policy.value
            model.scope = dict(scope)
            model.provenance = dict(provenance)
            model.updated_at = now
            session.flush()
            return _policy(model)

    def get_policy(
        self, repository_id: str, action: ProjectAction
    ) -> AuthorityPolicyEnvelope | None:
        with self.database.session() as session:
            model = session.scalar(
                select(CodeShopAuthorityPolicyModel).where(
                    CodeShopAuthorityPolicyModel.repository_id == repository_id,
                    CodeShopAuthorityPolicyModel.action == action.value,
                )
            )
            return _policy(model) if model is not None else None

    def list_policies(self, repository_id: str) -> list[AuthorityPolicyEnvelope]:
        with self.database.session() as session:
            models = session.scalars(
                select(CodeShopAuthorityPolicyModel)
                .where(CodeShopAuthorityPolicyModel.repository_id == repository_id)
                .order_by(CodeShopAuthorityPolicyModel.action)
            ).all()
            return [_policy(item) for item in models]

    def create_task(
        self,
        repository_id: str,
        *,
        title: str,
        capability: EngineeringCapability,
        source_backlog: dict[str, Any],
    ) -> EngineeringTask:
        self.get_project(repository_id)
        now = datetime.now(UTC)
        with self.database.session() as session:
            model = CodeShopTaskModel(
                id=str(uuid4()),
                repository_id=repository_id,
                title=title,
                capability=capability.value,
                state=EngineeringTaskState.QUEUED.value,
                source_backlog=dict(source_backlog),
                blocker=None,
                created_at=now,
                updated_at=now,
            )
            session.add(model)
            session.flush()
            return _task(model)

    def get_task(self, task_id: str) -> EngineeringTask:
        with self.database.session() as session:
            model = session.get(CodeShopTaskModel, task_id)
            if model is None:
                raise KeyError(f"Code Shop task {task_id!r} was not found")
            return _task(model)

    def list_tasks(
        self, repository_id: str | None = None, limit: int = 200
    ) -> list[EngineeringTask]:
        statement = select(CodeShopTaskModel)
        if repository_id is not None:
            statement = statement.where(CodeShopTaskModel.repository_id == repository_id)
        statement = statement.order_by(CodeShopTaskModel.created_at.desc()).limit(limit)
        with self.database.session() as session:
            return [_task(item) for item in session.scalars(statement).all()]

    def set_task_state(
        self,
        task_id: str,
        state: EngineeringTaskState,
        *,
        blocker: str | None = None,
    ) -> EngineeringTask:
        with self.database.session() as session:
            model = session.get(CodeShopTaskModel, task_id)
            if model is None:
                raise KeyError(f"Code Shop task {task_id!r} was not found")
            model.state = state.value
            model.blocker = blocker
            model.updated_at = datetime.now(UTC)
            session.flush()
            return _task(model)

    def record_attempt(
        self,
        task_id: str,
        *,
        status: str,
        approach: str,
        context_inputs: dict[str, Any],
        manager_provenance: dict[str, Any],
        touched_files: tuple[str, ...],
        command_summaries: tuple[str, ...],
        resources: dict[str, Any],
        outcome: dict[str, Any],
    ) -> EngineeringAttempt:
        self.get_task(task_id)
        now = datetime.now(UTC)
        with self.database.session() as session:
            maximum = session.scalar(
                select(func.max(CodeShopAttemptModel.number)).where(
                    CodeShopAttemptModel.task_id == task_id
                )
            )
            model = CodeShopAttemptModel(
                id=str(uuid4()),
                task_id=task_id,
                number=int(maximum or 0) + 1,
                status=status,
                approach=approach,
                context_inputs=dict(context_inputs),
                manager_provenance=dict(manager_provenance),
                touched_files=list(touched_files),
                command_summaries=list(command_summaries),
                resources=dict(resources),
                outcome=dict(outcome),
                created_at=now,
                finished_at=now if status in {"succeeded", "failed"} else None,
            )
            session.add(model)
            session.flush()
            return _attempt(model)

    def failed_attempt_count(self, task_id: str) -> int:
        with self.database.session() as session:
            count = session.scalar(
                select(func.count(CodeShopAttemptModel.id)).where(
                    CodeShopAttemptModel.task_id == task_id,
                    CodeShopAttemptModel.status == "failed",
                )
            )
            return int(count or 0)

    def record_decision(
        self,
        *,
        task_id: str,
        repository_id: str,
        module_id: str,
        action: ProjectAction,
        capability: ExecutionCapability,
        effective_decision: EffectiveDecision,
        risk_findings: tuple[str, ...],
        reason: str,
    ) -> AuthorityDecision:
        with self.database.session() as session:
            model = CodeShopAuthorityDecisionModel(
                id=str(uuid4()),
                task_id=task_id,
                repository_id=repository_id,
                module_id=module_id,
                action=action.value,
                capability=capability.value,
                effective_decision=effective_decision.value,
                risk_findings=list(risk_findings),
                reason=reason,
                created_at=datetime.now(UTC),
            )
            session.add(model)
            session.flush()
            return _decision(model)

    def create_escalation(
        self,
        task_id: str,
        *,
        reason: str,
        evidence: dict[str, Any],
        failed_invariant: str,
        recommended_capability: str,
        compact_handoff: str,
        dispositions: tuple[str, ...],
    ) -> Escalation:
        self.get_task(task_id)
        with self.database.session() as session:
            model = CodeShopEscalationModel(
                id=str(uuid4()),
                task_id=task_id,
                reason=reason,
                evidence=dict(evidence),
                failed_invariant=failed_invariant,
                recommended_capability=recommended_capability,
                compact_handoff=compact_handoff,
                dispositions=list(dispositions),
                status="open",
                created_at=datetime.now(UTC),
                resolved_at=None,
            )
            session.add(model)
            session.flush()
            return _escalation(model)

    def has_open_escalation(self, task_id: str) -> bool:
        with self.database.session() as session:
            value = session.scalar(
                select(func.count(CodeShopEscalationModel.id)).where(
                    CodeShopEscalationModel.task_id == task_id,
                    CodeShopEscalationModel.status == "open",
                )
            )
            return bool(value)

    def list_escalations(
        self, task_id: str | None = None, limit: int = 200
    ) -> list[Escalation]:
        statement = select(CodeShopEscalationModel)
        if task_id is not None:
            statement = statement.where(CodeShopEscalationModel.task_id == task_id)
        statement = statement.order_by(CodeShopEscalationModel.created_at.desc()).limit(limit)
        with self.database.session() as session:
            return [_escalation(item) for item in session.scalars(statement).all()]

    def record_outcome(
        self,
        task_id: str,
        *,
        attempt_id: str | None,
        kind: str,
        payload: dict[str, Any],
    ) -> OutcomeEvidence:
        self.get_task(task_id)
        with self.database.session() as session:
            model = CodeShopOutcomeEvidenceModel(
                id=str(uuid4()),
                task_id=task_id,
                attempt_id=attempt_id,
                kind=kind,
                payload=dict(payload),
                created_at=datetime.now(UTC),
            )
            session.add(model)
            session.flush()
            return _outcome(model)


def _project(model: CodeShopProjectModel) -> CodeShopProject:
    return CodeShopProject(
        repository_id=model.repository_id,
        full_name=model.full_name,
        visibility=model.visibility,
        default_branch=model.default_branch,
        lifecycle=ProjectLifecycle(model.lifecycle),
        priority=model.priority,
        branch_policy=dict(model.branch_policy or {}),
        metadata=dict(model.repository_metadata or {}),
        hosted_runner_eligible=model.hosted_runner_eligible,
        created_at=_utc(model.created_at),
        updated_at=_utc(model.updated_at),
    )


def _checkout(model: CodeShopCheckoutModel) -> CheckoutLink:
    return CheckoutLink(
        repository_id=model.repository_id,
        canonical_path=model.canonical_path,
        approved_root=model.approved_root,
        remote_identity=model.remote_identity,
        verified=model.verified,
        verification_detail=dict(model.verification_detail or {}),
        updated_at=_utc(model.updated_at),
    )


def _policy(model: CodeShopAuthorityPolicyModel) -> AuthorityPolicyEnvelope:
    return AuthorityPolicyEnvelope(
        repository_id=model.repository_id,
        action=ProjectAction(model.action),
        policy=ActionPolicy(model.policy),
        scope=dict(model.scope or {}),
        provenance=dict(model.provenance or {}),
        version=model.version,
        updated_at=_utc(model.updated_at),
    )


def _task(model: CodeShopTaskModel) -> EngineeringTask:
    return EngineeringTask(
        id=model.id,
        repository_id=model.repository_id,
        title=model.title,
        capability=EngineeringCapability(model.capability),
        state=EngineeringTaskState(model.state),
        source_backlog=dict(model.source_backlog or {}),
        blocker=model.blocker,
        created_at=_utc(model.created_at),
        updated_at=_utc(model.updated_at),
    )


def _attempt(model: CodeShopAttemptModel) -> EngineeringAttempt:
    return EngineeringAttempt(
        id=model.id,
        task_id=model.task_id,
        number=model.number,
        status=model.status,
        approach=model.approach,
        context_inputs=dict(model.context_inputs or {}),
        manager_provenance=dict(model.manager_provenance or {}),
        touched_files=tuple(model.touched_files or []),
        command_summaries=tuple(model.command_summaries or []),
        resources=dict(model.resources or {}),
        outcome=dict(model.outcome or {}),
        created_at=_utc(model.created_at),
        finished_at=_utc(model.finished_at) if model.finished_at else None,
    )


def _decision(model: CodeShopAuthorityDecisionModel) -> AuthorityDecision:
    return AuthorityDecision(
        id=model.id,
        task_id=model.task_id,
        repository_id=model.repository_id,
        module_id=model.module_id,
        action=ProjectAction(model.action),
        capability=ExecutionCapability(model.capability),
        effective_decision=EffectiveDecision(model.effective_decision),
        risk_findings=tuple(model.risk_findings or []),
        reason=model.reason,
        created_at=_utc(model.created_at),
    )


def _escalation(model: CodeShopEscalationModel) -> Escalation:
    return Escalation(
        id=model.id,
        task_id=model.task_id,
        reason=model.reason,
        evidence=dict(model.evidence or {}),
        failed_invariant=model.failed_invariant,
        recommended_capability=model.recommended_capability,
        compact_handoff=model.compact_handoff,
        dispositions=tuple(model.dispositions or []),
        status=model.status,
        created_at=_utc(model.created_at),
        resolved_at=_utc(model.resolved_at) if model.resolved_at else None,
    )


def _outcome(model: CodeShopOutcomeEvidenceModel) -> OutcomeEvidence:
    return OutcomeEvidence(
        id=model.id,
        task_id=model.task_id,
        attempt_id=model.attempt_id,
        kind=model.kind,
        payload=dict(model.payload or {}),
        created_at=_utc(model.created_at),
    )


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
