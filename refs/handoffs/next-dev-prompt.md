---
type: Development Prompt
title: Next Development Prompt
description: Ready-to-use prompt for install-time module permission review.
status: stable
tags: [nerve-center, handoff, modules, permissions, safety]
---
# Next Development Prompt

Continue implementation directly on `dev`. Do not create a feature branch or PR. Do not promote `qa` or `main` unless explicitly requested.

Issue #62 is implemented. The next active bounded slice is Issue #63: **Add install-time module permission review foundation**.

Start with:

```powershell
python scripts/agent_context.py --focus "module permission review install update manifest required approval lifecycle authority" --issue 63
```

Use packet-first/progressive loading. Read only:

1. `refs/handoffs/currentHandoff.md`
2. Issue #63 and its latest comments
3. `refs/planning/mvp-roadmap.md` around Increment 13
4. source-catalog matches for module manifest permissions, module synchronization/lifecycle, persistence, manager API, and Code Shop authority/risk seams
5. validation commands returned by the packet

## Accepted baseline

Issue #62 implementation checkpoint: `66bee379efc7ba41c5fe17a0a9a7c129522c5467`.

Lint correction: `8e1914fe2d88f47f47bf1ba3dc63801cb6de5b63`.

Generated discovery checkpoint: `4841ea65b3b98a562bad73a5d2f0e73ef83b3ca8`.

Application version: `0.12.29`. Database schema: 13.

Bounded #62 validation passed source catalog 206 files / 1750 symbols, 11 OKF indexes, refs/context checks, Ruff, 20 focused tests, 290 total Python tests, desktop web, and desktop Rust/Tauri.

The morning summary is SELECT-only durable projection state. Attention/Review remains the authoritative human queue. Volatile module-runtime health is not persisted merely to appear in the summary.

## Issue #63 bounded target

Implement manager-owned install/update permission review:

- deterministic normalized manifest permission requests;
- durable pending/approved/denied review state keyed to exact module/version/permission fingerprint;
- decision actor/provenance;
- no synthetic review for modules that declare no permissions;
- required unreviewed permission changes block operational enablement;
- minimal inspect/approve/deny manager API;
- approval only for declared permissions;
- changed permission request invalidates stale approval;
- permission approval remains separate from official-module trust and cannot bypass Code Shop/action authority or manager risk gates.

Explicitly defer actual authenticated/private connectors, credential UX/storage, external drafts/writes, third-party marketplace/sandboxing, learned permission policy, and polished desktop UI.

Validate the full repository contract, then update Issue #63 and both handoffs with exact final commit/CI evidence.
