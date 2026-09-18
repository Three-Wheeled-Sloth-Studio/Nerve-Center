---
type: Development Prompt
title: Next Development Prompt
description: Ready-to-use prompt for the Code Shop safe orchestration foundation.
status: stable
tags: [nerve-center, handoff, code-shop, orchestration, safety]
---
# Next Development Prompt

Continue implementation directly on `dev`. Do not create a feature branch or PR. Do not promote `qa` or `main` unless explicitly requested.

Issue #57 and Issue #60 are closed as completed. The next active bounded slice is Code Shop Issue #54: **Establish safe orchestration foundation**.

Start with:

```powershell
python scripts/agent_context.py --focus "Code Shop safe orchestration foundation project registry checkout authority execution host" --issue 54
```

Use packet-first/progressive loading. Read:

1. `refs/handoffs/currentHandoff.md`
2. Issue #54 and its latest comments
3. only source-catalog matches returned for the Code Shop foundation
4. relevant validation commands from the generated agent-context packet

Do not reread repository history or broadly scan unrelated Job Scout code.

## Accepted baseline

The final Job Scout provider/cache acceptance run is `5d3f2ad8-2c01-4dde-b640-0ae467585d35` from exact Git `0169e148de9b56e571c525a6a920bed654e7c303` with `uses_checkout_source=true`. It reached planned `admission_draining` with 67 / 150 requests and 7 / 30 LLM calls, completed four full scores with zero failures, and recorded four run-scoped public-search calls.

All four searches were `duckduckgo_html` network calls with `status=succeeded`, no fallback flag, and no challenge. Aggregate `search_provider_fallbacks=0` therefore matches the per-search evidence exactly. No Bing call was required or forced merely to exercise the fallback path. Issue #60 is accepted and closed.

Do not reopen Job Scout provider policy, query semantics, scoring, scheduler weights, cooldown duration, request caps, extraction rules, or add a third provider without new evidence.

## Issue #54 architecture contract

Preserve the accepted Code Shop foundation:

- Code Shop is the permanent display name; stable module/storage ID is `code_shop`.
- GitHub is authoritative for repository identity, visibility, default branch, and repository metadata.
- Nerve Center persists project selection, lifecycle, priority, authority policy, and machine-local checkout linkage keyed by stable GitHub repository identity.
- Local paths are not repository identity and are not portable project truth.
- Linked checkouts must be contained inside manager-approved roots and their Git remote must match the selected GitHub repository before execution is admitted.
- Code Shop is model-blind and requests named capabilities rather than models.
- Privileged local execution remains behind a manager-owned typed capability contract; no generic module-owned shell authority.
- Consequential actions may run without per-action confirmation only under the trusted-module, declared-capability, explicit-project-policy, durable-task, scope-validation, and risk-evaluation contract in Issue #54.
- Deployment, credential/secret mutation, destructive Git operations, irreversible data changes, and equivalent high-risk actions remain escalation-gated.

## Bounded implementation target

Implement the smallest coherent Issue #54 foundation that satisfies its acceptance criteria without pulling later autonomous-coding features forward. Keep concerns atomic and source-catalog discoverable.

The slice should establish, as needed by the existing architecture:

1. official Code Shop module registration with manager-derived trust provenance;
2. GitHub-backed durable project registry and lifecycle states;
3. machine-local checkout association with containment and remote-identity validation;
4. project action policy `allow | ask | deny` plus separate risk escalation;
5. typed privileged execution-host capability contract with deterministic/no-op test adapter only;
6. durable engineering task, attempt/outcome, authority-decision, and escalation records;
7. model-blind capability vocabulary for planning, decomposition, implementation, debugging, review, and research;
8. minimal manager API surface required to exercise and test those contracts;
9. deterministic boundary/regression tests.

Explicitly defer unrestricted shell access, production GitHub mutation, hosted-runner execution, autonomous deployment/credential changes, destructive Git, premium-agent escalation, learned policy mutation, self-modification, and polished dashboard UI.

Validate using the repository's generated validation contract and update the handoff/Issue #54 with the exact landed commit and CI evidence.
