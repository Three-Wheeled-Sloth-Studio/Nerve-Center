---
type: Architecture Overview
title: Nerve Center Product Vision and Architecture
description: Compact architectural summary of Nerve Center manager ownership, module responsibilities, external-action boundaries, and design principles.
status: stable
tags: [nerve-center, planning, architecture]
---
# Nerve Center Product Vision and Architecture

> The authoritative product definition is `refs/planning/product-requirements-document.md`. This document is the compact architectural summary.

## Vision

Nerve Center is a single-user, local-first orchestration runtime for long-horizon unattended work. A user authorizes bounded wall-clock sessions in which independently packaged modules can discover and process work while sharing manager-owned scheduling, resources, durable state, model infrastructure, review surfaces, and updates.

The core product is the manager. Job Scout and future workflows such as Asset Forge or Wordsmith are first-party reference modules, not core product features. Their domain logic, configuration, records, and views must remain separable from the manager.

## Architectural shape

```text
Tauri desktop shell and manager-owned UX
        |
Local manager API and event channel
        |
Orchestration core
  | wall-clock sessions and scheduler
  | module lifecycle and process supervision
  | durable task and result queue
  | normalized module priorities
  | resource and concurrency budgets
  | provider-neutral LLM manager
  | Model Lab and performance learning
  | Attention and Review infrastructure
  | backup, migration, and update coordination
        |
Manager-launched module processes
  | Job Scout
  | future first-party modules
        |
Persistence boundary
  | local mode: SQLite, module namespaces, and isolated artifact directories
  | hosted mode (post-MVP): PostgreSQL behind the same repository contracts
```

The desktop shell is not the business-logic host. Core scheduling, persistence, queueing, model orchestration, module supervision, and update behavior live behind reusable local service contracts.

## Core platform responsibilities

- Resolve duration-based and fixed-time schedules to concrete wall-clock sessions.
- Launch, supervise, pause, update, and stop independent module processes.
- Allocate exactly 100 module-priority points across enabled modules.
- Enforce request, network, model, storage, cloud-spend, and elapsed-time budgets.
- Own every LLM and provider call; modules remain model-blind.
- Order requests using module priority, request age, model suitability, and model-switch cost.
- Report queue depth and wait estimates to modules and users.
- Persist tasks before acknowledgement and redeliver unacknowledged results.
- Discover, evaluate, install, and benchmark local models within user policy.
- Store durable data outside the checkout and snapshot before migrations.
- Coordinate compatible core and module updates through stable and dev channels.
- Present unified status, queue, review, attention, and diagnostics surfaces.

## Module responsibilities

Modules own domain work. They may perform deterministic and network work in their own threads or processes during an authorized session, queue typed LLM requests through the manager, throttle when queue pressure is high, and stop discovery when the manager begins draining.

Modules provide domain configuration and module-specific UI panels within the manager-owned shell. They may contribute structured status and alerts to reserved dashboard cards, but may not replace core navigation, provider policy, queue policy, security settings, or the design system.

## Consequential-action boundary

The system may analyze, recommend, draft, transform, package, and stage. It does not submit, send, publish, purchase, accept terms, alter accounts, or perform comparable unattended external actions.

Authenticated read and non-public remote drafts may be supported only through explicit manager-owned connectors. Automated publishing and other autonomous external-action products remain outside Nerve Center.

## Design principles

- The manager exclusively owns the LLM boundary.
- Wall clock is authoritative for run windows.
- Structured durable state is authoritative.
- Modules are independently packaged and supervised.
- Local execution with local SQLite storage is the default. A post-MVP hosted mode may run the same manager contracts against PostgreSQL without weakening module boundaries or silently synchronizing local data.
- Provider and model choices remain manager concerns.
- Reversible actions favor undo over unnecessary confirmation.
- Human review precedes consequential external action.
- Progressive disclosure keeps ordinary operation understandable while preserving deep diagnostics.
