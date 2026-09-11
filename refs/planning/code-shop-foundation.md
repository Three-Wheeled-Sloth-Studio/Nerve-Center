---
type: Architecture Contract
title: Code Shop Foundation
description: Accepted first-slice architecture for safe, model-blind software-engineering orchestration.
status: stable
tags: [nerve-center, code-shop, modules, security, orchestration]
---
# Code Shop Foundation

**Issue:** #54  
**Stable module ID:** `code_shop`  
**Storage namespace:** `code_shop`

## Purpose and boundary

Code Shop is Nerve Center's second first-party reference module. It owns project backlog
orchestration, task decomposition, engineering workflow state, escalation decisions, and
module-specific dashboard data. The manager continues to own module trust, repository
connectors, permissions, authority evaluation, credentials, scheduling, resource budgets,
provider/model routing, durable shared work delivery, and privileged local execution.

Code Shop never receives unrestricted shared-database, provider, credential, filesystem, or
shell access. The first slice establishes contracts and deterministic boundaries; it does not
enable production GitHub mutation, hosted runners, deployment, destructive Git, external-agent
escalation, or learned policy mutation.

## Repository and checkout model

GitHub is authoritative for repository identity, owner/name, visibility, default branch, and
other repository metadata. A manager-owned connector discovers repositories visible to the
configured GitHub identity. The local registry stores Code Shop selection and policy keyed to
the stable GitHub repository identifier even when no checkout is linked.

A user may link a discovered repository to a machine-local checkout folder. Before admitting
local execution, the manager canonicalizes the path, proves it is inside an approved checkout
root and the registered checkout, and verifies that the checkout's Git remote matches the
selected GitHub identity. Checkout paths are local associations, not portable project truth.
Moving or unlinking a checkout does not change repository identity.

Project lifecycle states are `enabled`, `paused`, `observe_only`, `needs_attention`, and
`excluded`. Only an enabled, correctly linked project may admit mutating local execution.
Observe-only projects may inspect GitHub and linked checkout state but may not mutate either.

## Authority evaluation

Project action policy uses `allow`, `ask`, and `deny`. It is evaluated as an intersection, not
as a grant emitted by the module:

```text
official module trust
  + declared module capability
  + explicit user project policy
  + durable task attribution
  + repository / checkout / branch / resource scope
  + manager risk decision
  = execute, request attention, or deny
```

Official trust is manager-derived installation provenance and cannot be asserted in a module
request or manifest payload. An ordinary `allow` never overrides manager-prohibited actions.
Deployment, credential or secret mutation, destructive Git operations, irreversible data
changes, and equivalent hazards are prohibited or require explicit human handling. Promotion
toward protected release branches is attention-required by default and remains distinct from
ordinary integration-branch work.

The initial policy vocabulary covers checkout read/write, branch creation, commit, push,
issue mutation, PR mutation, integration merge, release promotion, workflow trigger,
hosted-runner execution, dependency modification, CI/workflow modification, deployment,
credential mutation, and destructive Git. It is extensible without changing stored task state.

## Privileged execution host

The manager exposes typed capabilities rather than `shell=True`. Initial contract vocabulary:

- `repo.read`, `repo.write`;
- `git.branch`, `git.commit`, `git.push`, `git.integration_merge`;
- `shell.execute`, `test.execute`;
- `github.repo.read`, `github.issue.read`, `github.issue.write`;
- `github.pr.read`, `github.pr.write`, `github.workflow.trigger`;
- `runner.execute`, `web.read`.

Every request identifies its Code Shop task, project, capability, bounded arguments, expected
outputs, timeout/resource limits, and idempotency key. The host records the authority decision,
resolved checkout, command/action class, sanitized result, and provenance. The first slice uses
a deterministic adapter to prove admission and denial behavior without running production
commands or GitHub writes. A separately supervised privileged host may replace the adapter
behind the same contract later.

## Durable domain model

Manager-owned project and authority records:

- project: stable GitHub identity, synchronized metadata, lifecycle, priority, branch policy,
  validation guidance pointers, compatibility metadata, hosted-runner eligibility;
- checkout link: machine-local canonical path, approved root, verified remote identity, and
  last verification outcome;
- authority envelope: action, `allow`/`ask`/`deny`, scope, user decision provenance, and version;
- authority decision: requested action, effective decision, risk findings, and durable task.

Code Shop-owned orchestration records:

- engineering task: project, source backlog item, capability needs, workflow state, blocker;
- attempt: approach, context packet inputs, capability/provider provenance supplied by the
  manager, touched-file and command/test summaries, resources, and outcome;
- escalation: reason, bounded attempt evidence, failed invariant, recommended capability/tool
  class, compact handoff, and allowed user dispositions;
- outcome evidence: validation, CI, PR, merge/revert, user override, and elapsed-resource facts.

Engineering workflow states are `queued`, `planning`, `in_progress`, `validating`,
`waiting_on_ci`, `waiting_on_runner`, `waiting_on_external_dependency`, `needs_user_input`,
`escalation_recommended`, `completed`, and `failed_or_abandoned`. GitHub-specific facts remain
provenance rather than generic workflow states.

## Model-blind capability requests

Code Shop requests `architecture_planning`, `task_decomposition`, `code_implementation`,
`debugging`, `code_review`, or `research`. The existing manager/provider boundary selects a
provider and model using task requirements and evidence. Code Shop cannot name or directly
invoke a production model. Existing queue work classes, session behavior, provider evidence,
and Model Lab experimental isolation remain unchanged.

## First implementation slice

1. Register the built-in official Code Shop module and manager-owned trust provenance.
2. Add additive persistence and repositories for projects, checkout links, authority policy,
   engineering work, attempts/outcomes, authority decisions, and escalations.
3. Add GitHub repository discovery and synchronization behind a manager connector contract;
   tests use a deterministic connector.
4. Add checkout linking, canonical containment, and remote-identity verification.
5. Add pure authority/risk evaluation and the typed execution-host request contract.
6. Add minimal manager APIs to inspect and configure projects, tasks, authority, and
   escalations.
7. Add a minimal managed worker/operation bridge sufficient to prove module isolation and
   model-blind capability submission.
8. Add deterministic critical tests from Issue #54 and run the full repository validation set.

Implementation proceeds directly on `dev` under the current user directive. No feature branch
or pull request is created for this slice; coherent validated commits are pushed to GitHub and
Issue #54 remains the work ledger.
