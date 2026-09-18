---
type: Development Prompt
title: Next Development Prompt
description: Ready-to-use prompt for the manager morning summary foundation.
status: stable
tags: [nerve-center, handoff, summary, attention, reporting]
---
# Next Development Prompt

Continue implementation directly on `dev`. Do not create a feature branch or PR. Do not promote `qa` or `main` unless explicitly requested.

Issue #61 is implemented. The next active bounded slice is Issue #62: **Add manager morning summary foundation**.

Start with:

```powershell
python scripts/agent_context.py --focus "manager morning summary completed blocked failed degraded comparison attention" --issue 62
```

Use packet-first/progressive loading. Read only:

1. `refs/handoffs/currentHandoff.md`
2. Issue #62 and its latest comments
3. `refs/planning/mvp-roadmap.md` around Increment 13
4. source-catalog matches for durable runs/work queue, Attention/Review, module/runtime durable evidence, Model Lab comparison results, and manager API seams
5. validation commands returned by the packet

## Accepted baseline

Issue #61 implementation checkpoint: `dd58e0c338afea5a066efcc8f663d47cd878f048`.

Generated discovery checkpoint: `bbdae93b3cce5f04efa02b3783bebb625fd47ab3`.

Application version: `0.12.28`. Database schema: 13.

Bounded validation run `35356015569` passed 17 focused tests, 287 total Python tests, refs/source/OKF/context checks, Ruff, desktop web, and desktop Rust/Tauri.

Attention/Review is manager-owned durable state. Open items block only declared dependency keys; module context/dispositions cannot grant authority. Code Shop escalations link to Attention without changing the whole project lifecycle.

## Issue #62 bounded target

Build a read-only manager morning summary:

- explicit requested time window; do not infer sleep/wake times;
- completed, failed, blocked/attention-required, degraded, and comparison/review categories only where durable evidence already supports them;
- stable source/module attribution for every surfaced item;
- pending Attention items linked, not copied into a second queue;
- minimal read-only API;
- deterministic empty/mixed-window, restart, and no-mutation tests.

Explicitly defer scheduled delivery, external notifications/messages/connectors, polished UI, install-time permissions, automatic remediation, and LLM-authored narrative.

Validate the full repository contract, then update Issue #62 and both handoffs with exact final commit/CI evidence.
