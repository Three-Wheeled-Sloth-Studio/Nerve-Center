---
type: Handoff
title: Current Handoff
description: Active Nerve Center implementation state and the next context-heavy checkpoints.
status: stable
tags: [nerve-center, handoff]
---
# Current Handoff

## Current state

- `dev` is the accepted integration branch.
- Current application version on the alignment baseline is `0.12.4`.
- The latest accepted implementation checkpoint makes Job Scout scans scheduler-ready.
- Earlier accepted checkpoints cover module contracts, durable runs, provider-neutral local LLM support, career evidence, job discovery, scoring, application tracking, Tauri desktop review, and Windows packaging/runtime bootstrap.
- Historical checkpoint detail remains in the sibling files under `refs/handoffs/`.

## Current documentation work

Nerve Center is being aligned non-destructively with Agent Academy's OKF v0.2-compatible project-memory profile. Existing project-specific refs remain authoritative; the alignment adds discovery, validation, path-safety, and interoperability contracts around them.

## Validation boundary

Before promoting this alignment, run the commands in `refs/testing/validationCommands.yaml`, including generated-index checks and the tracked-path case-collision guard, plus the existing Python, React/TypeScript, Rust/Tauri, and Windows packaging gates where applicable.
