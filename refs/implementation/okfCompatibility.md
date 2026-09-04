---
type: Compatibility Contract
title: Nerve Center Agent Academy OKF Compatibility
description: Authority boundaries and interoperability rules for Nerve Center's Agent Academy OKF v0.2 profile.
status: stable
tags: [nerve-center, agent-academy, okf, interoperability]
---
# Nerve Center Agent Academy OKF Compatibility

Nerve Center is a mature custom refs repository. Agent Academy provides the operating model; OKF provides a portable representation and discovery surface. Alignment must not replace stronger Nerve Center project truth with generic template structure.

## Authority

- `refs/agents.yaml` is the operating-instruction authority.
- Existing Nerve Center planning, engineering, handoff, research, and testing documents remain authoritative in their established domains.
- Structured YAML is authoritative where exact machine state or validation semantics are required.
- Markdown files under `refs/`, except reserved `index.md` and `log.md`, are OKF concepts.
- Generated indexes are discovery artifacts only. They never override the originating concept or structured resource.

## Provenance and trust

Do not add `generated`, `verified`, `sources`, or `stale_after` merely to appear more conformant. `verified` means an actor actually checked the concept against its source; tests, Git history, generated indexes, and refs validation do not imply verification.

## Studio catalog

A future studio-wide catalog may index this bundle by repository, commit SHA, bundle path, and concept path. The catalog is derived navigation. Nerve Center remains the source of truth for Nerve Center knowledge.
