---
type: Development Prompt
title: Next Development Prompt
description: Ready-to-use prompt for manager-owned backup and pre-migration snapshots.
status: stable
tags: [nerve-center, handoff, backups, durability, migrations, safety]
---
# Next Development Prompt

Continue implementation directly on `dev`. Do not create a feature branch or PR. Do not promote `qa` or `main` unless explicitly requested.

Issue #64 is implemented. Job Scout relevance-quality follow-up Issue #66 is also implemented without changing application version or database schema. The next active bounded slice is Issue #65: **Add manager-owned backup and pre-migration snapshot foundation**.

Start with:

```powershell
python scripts/agent_context.py --focus "backup pre-migration snapshot sqlite WAL module data retention verification restore eligibility path containment" --issue 65
```

Use packet-first/progressive loading. Read only:

1. `refs/handoffs/currentHandoff.md`
2. Issue #65 and its latest comments
3. `refs/planning/mvp-roadmap.md` around Increment 14
4. source-catalog matches for database initialization/migration, runtime data roots, module storage, persistence metadata, and manager APIs
5. validation commands returned by the packet

## Accepted baseline

Issue #64 implementation checkpoint: `7281c49799bac21a6dab6083c7b6d988b95e27ae`.

Lint correction: `6735debe949dbb4db73b10114988a98ef4f2786a`.

Generated discovery checkpoint: `41d09d070a7fabb0a3fda3e68d743a53452b28de`.

Application version: `0.12.31`. Database schema: 15.

Bounded #64 validation run `35370973810` passed source catalog 219 files / 1837 symbols, 11 OKF indexes, initialized refs validation, 7,055-character agent-context validation, Ruff, 33 focused tests, 301 total Python tests, desktop web, and desktop Rust/Tauri.

Closeout catalog/handoff-index refresh: `7cd76e51ff43ebcd7188ee9c3cd0cd422b418f70`. Final #64 standard CI: `35372662394` on exact code/version head `b309c52cfb2e5f5dae6629f1642b25edfa0349a3`, all Python / desktop-web / desktop-rust jobs green with 301 Python tests.

Job Scout Issue #66 keeps gap reflection aligned with configured career intent. Capability phrases are no longer invented into `"... company"` archetypes, arbitrary legacy `local_employer` anchors are rejected before network spend, senior-target reflections reject internship/entry-level and non-role activity anchors, and stale malformed archetype labels no longer perpetuate coverage gaps. Reflection contract is v3. Provider policy, scheduler weights, request caps, ranking/scoring, application version `0.12.31`, and schema 15 are unchanged.

Resource profiles are manager-owned. Only `max_requests`, `max_llm_calls`, and `max_parallel_work` are currently enforced. Memory, VRAM, queue depth, and exploration are inspectable but unenforced. Cloud spend is explicitly `unenforced_no_authority`. Profiles cannot grant module permission or Code Shop/action authority.

## Issue #65 bounded target

Implement the manager-owned backup/pre-migration snapshot foundation:

- durable backup records with stable ID, kind, source schema version, status, verified path, size/hash, and safe provenance;
- one manager-controlled local backup root outside the source checkout;
- SQLite-safe backup semantics for active WAL state rather than raw-copying the database;
- bounded deterministic inclusion of durable module data beneath the manager runtime data root;
- artifact verification for existence, hash/integrity, and expected SQLite schema;
- an explicit pre-migration snapshot operation that performs no migration;
- minimal manager APIs to create/list/read/verify backups;
- bounded retention sufficient for a lightweight daily-backup policy without speculative scheduling;
- path-containment, active-WAL, restart, missing/tampered/corrupt artifact, and authority-boundary regressions.

Explicitly defer update download/staging/apply/rollback, live restore execution, cloud backup/sync, encryption/key-management UX, and third-party migration hooks.

Validate the full repository contract, then update Issue #65 and both handoffs with exact landed commit/CI evidence.
