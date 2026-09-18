---
type: Development Prompt
title: Next Development Prompt
description: Ready-to-use prompt for manager-owned reusable resource profiles.
status: stable
tags: [nerve-center, handoff, resources, sessions, safety]
---
# Next Development Prompt

Continue implementation directly on `dev`. Do not create a feature branch or PR. Do not promote `qa` or `main` unless explicitly requested.

Issue #63 is implemented. The next active bounded slice is Issue #64: **Add manager-owned reusable resource profile foundation**.

Start with:

```powershell
python scripts/agent_context.py --focus "resource profiles session overrides CPU memory GPU VRAM concurrency queue network exploration cloud spend authority" --issue 64
```

Use packet-first/progressive loading. Read only:

1. `refs/handoffs/currentHandoff.md`
2. Issue #64 and its latest comments
3. `refs/planning/mvp-roadmap.md` around Increment 14
4. source-catalog matches for existing run/session budgets, resource limits, queue depth, provider request limits, manager persistence/API, and Code Shop authority/risk seams
5. validation commands returned by the packet

## Accepted baseline

Issue #63 implementation checkpoint: `4a2ad34772668334cf0e0e74106d60ed71d4e392`.

Compatibility-test corrections through: `ceb710fc35398718366a43ab6d4576a8c3117216`.

Generated discovery checkpoint: `7345692fc40e385c57536fd7c44fd49ee6f9e12a`.

Application version: `0.12.30`. Database schema: 14.

Bounded #63 validation run `35363736308` passed source catalog 212 files / 1792 symbols, 11 OKF indexes, initialized refs validation, 7,054-character agent-context validation, Ruff, 27 focused tests, 297 total Python tests, desktop web, and desktop Rust/Tauri.

Permission review is manager-owned and version/fingerprint-specific. Fresh required permissions block operational enablement until approved; identical permission sets can carry decisions forward with explicit provenance; changed sets become pending. Permission approval is distinct from official-module trust and cannot bypass Code Shop/action authority or manager risk evaluation.

## Issue #64 bounded target

Implement manager-owned reusable resource profiles:

- durable named profiles with manager-owned identity and display name;
- deterministic effective resolution: explicit session override > selected named profile > manager default;
- bounded representation for CPU/concurrency, memory, GPU/VRAM, queue depth, network/request, exploration, and optional cloud-spend ceilings only where current contracts can represent them honestly;
- missing values inherit; invalid/negative values are rejected rather than treated as unlimited;
- explicit distinction between enforced and currently unenforced fields;
- minimal manager APIs to list/read/create/update/select profiles;
- integrate only existing session/run/provider budget seams without duplicating module-owned configuration;
- prove modules cannot raise manager ceilings through task/module configuration;
- prove resource profiles do not grant module permission, Code Shop authority, external-action capability, or cloud-spend authority.

Explicitly defer hardware benchmarking/autotuning, idle/battery/metered-network sensing, update staging/rollback, automatic cloud spend escalation, and polished desktop profile editing.

Validate the full repository contract, then update Issue #64 and both handoffs with exact landed commit/CI evidence.
