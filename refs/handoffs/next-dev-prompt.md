---
type: Development Prompt
title: Next Development Prompt
description: Ready-to-use prompt for the manager-owned Attention and Review queue foundation.
status: stable
tags: [nerve-center, handoff, attention, review, orchestration, safety]
---
# Next Development Prompt

Continue implementation directly on `dev`. Do not create a feature branch or PR. Do not promote `qa` or `main` unless explicitly requested.

Issue #54 is implemented. The next active bounded slice is Issue #61: **Add manager-owned Attention and Review queue foundation**.

Start with:

```powershell
python scripts/agent_context.py --focus "manager attention review queue dependency blocking Code Shop escalation" --issue 61
```

Use packet-first/progressive loading. Read:

1. `refs/handoffs/currentHandoff.md`
2. Issue #61 and its latest comments
3. `refs/planning/mvp-roadmap.md` only around Increment 13 / Attention and Review
4. only source-catalog matches returned for attention/review, Code Shop escalation, persistence, and manager API seams
5. relevant validation commands returned by the generated packet

Do not reread repository history or reopen accepted Job Scout/Code Shop foundation decisions.

## Accepted baseline

Code Shop foundation implementation checkpoint: `6112a760cdb00821c5fdefdeff695b7a46559076`.

Generated discovery-artifact checkpoint: `4f90c65bb7cfb260f795d27b8c0bc4cbf1df7c0f`.

Application version: `0.12.27`. Database schema: 12.

The manager now owns Code Shop project identity/lifecycle, checkout verification, explicit action authority, risk evaluation, typed execution-host requests, and durable engineering task/attempt/outcome/decision/escalation state. The Code Shop worker is model-blind and has no direct privileged execution authority. The current execution host is deliberately deterministic/no-op.

Do not expand production shell, GitHub mutation, hosted-runner, deployment, credential, destructive-Git, premium-agent, or learned-policy authority in Issue #61.

## Issue #61 bounded target

Implement generic manager-owned Attention and Review primitives rather than another module-specific human-review mechanism:

1. durable Attention/Review item identity, state, context, allowed dispositions, validation/downstream meaning, and audit history;
2. idempotent module submission;
3. explicit dependency keys/links so a pending item blocks only dependent workflow branches;
4. minimal manager API to create/list/read/resolve/dismiss items and inspect history;
5. Code Shop escalation linkage to exactly one manager Attention item while preserving Code Shop-specific evidence;
6. deterministic restart, idempotency, and dependency-isolation tests.

Module-provided context and dispositions are descriptive inputs only. They must not grant capabilities, change project authority, or override manager risk decisions.

Explicitly defer morning summary delivery, polished desktop queue UI, install-time module permission review, authenticated/private connector expansion, external draft/write connectors, and any consequential-action expansion.

Validate with the repository's generated validation contract. Update Issue #61 and both handoff files with exact commit/CI evidence before advancing.
