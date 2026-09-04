---
type: Migration Guide
title: Nerve Center Agent Academy OKF Adoption
description: Non-destructive adoption and future upgrade guidance for Nerve Center's mature refs repository.
status: stable
tags: [nerve-center, agent-academy, okf, migration]
---
# Nerve Center Agent Academy OKF Adoption

The 2026-09 alignment adopts Agent Academy's OKF v0.2 compatibility profile without replacing Nerve Center's established refs taxonomy.

## Adoption rules

- Preserve existing Nerve Center Markdown content and deterministic state.
- Add OKF frontmatter to existing Markdown concepts without rewriting their substance merely for migration.
- Pin the Agent Academy and canonical OKF baselines in `refs/okfProfile.yaml`.
- Commit deterministic generated indexes.
- Extend normal validation with refs conformance and tracked-path case-collision checks.
- Keep project-specific exceptions explicit instead of importing duplicate blank template files.

## Future profile upgrades

Treat a new OKF or Agent Academy profile version as an explicit migration: review upstream changes, update exact pinned baselines, adjust validation only where required, regenerate indexes, and validate Nerve Center before promoting the profile further.
