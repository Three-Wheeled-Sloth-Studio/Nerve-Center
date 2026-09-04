---
type: Project Memory Guide
title: Nerve Center Refs Guide
description: Reading order, authority boundaries, and maintenance rules for Nerve Center project memory.
status: stable
tags: [nerve-center, project-memory, agent-academy, okf]
---
# Nerve Center Refs Guide

Nerve Center uses a mature custom `refs/` layout aligned with the current Agent Academy project-memory harness. The alignment is additive: existing Nerve Center planning, engineering, handoff, research, and testing documents remain authoritative rather than being duplicated into blank template taxonomy.

The `refs/` directory is also an Open Knowledge Format (OKF) v0.2 bundle. Deterministic YAML remains authoritative for exact state and validation, Markdown knowledge documents use OKF frontmatter, and generated `index.md` files provide portable discovery.

## Required reading order

1. `refs/project.yaml`
2. `refs/agents.yaml`
3. `refs/planning/mvp-roadmap.md`
4. `refs/planning/decision-register.md`
5. `refs/planning/product-vision-and-architecture.md` before architecture changes
6. `refs/implementation/fileMap.yaml` before broad code search
7. `refs/testing/validationCommands.yaml` before finalizing work
8. `refs/handoffs/currentHandoff.md` for the latest context-heavy checkpoint

Use `refs/index.md` for discovery, but do not substitute it for the required reading order.

## Maintenance

- Preserve Nerve Center's existing refs organization when it is useful.
- Keep durable decisions, task state, architecture notes, validation guidance, and handoffs in `refs/` rather than only in chat.
- Preserve OKF frontmatter on every non-reserved Markdown file under `refs/`.
- Do not hand-edit generated `index.md` files.
- Regenerate indexes with `python refs/tools/generate_okf_indexes.py`.
- Validate with `python refs/tools/validate_refs.py --mode initialized`.
- Never infer OKF `verified` status from generation, passing tests, Git history, or refs validation.
- Do not store secrets, tokens, API keys, passwords, or machine-only credentials in `refs/`.
