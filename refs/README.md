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

Nerve Center also maintains a deterministic generated source catalog under `refs/implementation/sourceCatalog/`, with sharded detail in `refs/implementation/.sourceCatalogShards/`. It lets coding agents locate relevant files and callable symbols without spending context on broad source-tree reads. The catalog is static-analysis evidence only; source and tests remain authoritative.

## Routine coding-agent re-entry

For routine continuation or after a context reset, begin with:

```powershell
python scripts/agent_context.py --focus "<short task description>" --issue <issue-number>
```

Ordinary packet generation refreshes the source catalog programmatically before selecting context. Start with the packet's explicit required reads and source-catalog matches. If implementation ownership is still unclear, query:

```powershell
python refs/tools/generate_source_catalog.py --query "<task or symbol>"
```

Prefer the reported symbol or line range over opening an entire source file. Expand to broader planning, architecture, history, or source only for a concrete dependency, ambiguity, failing test, system boundary, or authoritative reference.

## Authoritative reading order when deeper context is needed

1. `refs/project.yaml`
2. `refs/agents.yaml`
3. `refs/planning/mvp-roadmap.md`
4. `refs/planning/decision-register.md`
5. `refs/planning/product-vision-and-architecture.md` before architecture changes
6. `refs/implementation/fileMap.yaml` when catalog evidence is insufficient
7. `refs/testing/validationCommands.yaml` before finalizing work
8. `refs/handoffs/currentHandoff.md` for the latest context-heavy checkpoint

Use `refs/index.md` for knowledge discovery and `refs/implementation/sourceCatalog/index.yaml` for compact implementation discovery. Neither substitutes for authoritative source or refs.

## Maintenance

- Preserve Nerve Center's existing refs organization when it is useful.
- Keep durable decisions, task state, architecture notes, validation guidance, and handoffs in `refs/` rather than only in chat.
- Keep `Required Reads For Next Slice` in the active handoff narrow: list only files, symbols, or line ranges the next agent actually needs and state why.
- Preserve OKF frontmatter on every non-reserved Markdown file under `refs/`.
- Do not hand-edit generated `index.md` or source-catalog files.
- Regenerate indexes with `python refs/tools/generate_okf_indexes.py` and the source catalog with `python refs/tools/generate_source_catalog.py`.
- Validate with `python refs/tools/generate_source_catalog.py --check` and `python refs/tools/validate_refs.py --mode initialized`.
- Never infer OKF `verified` status from generation, passing tests, Git history, or refs validation.
- Do not store secrets, tokens, API keys, passwords, or machine-only credentials in `refs/`.
