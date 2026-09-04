---
type: Module Contract
title: Module Package Contract
description: Accepted manager/module ownership, manifest, lifecycle, storage, permissions, UI contribution, process runtime, and durable-work contract.
status: stable
tags: [nerve-center, planning, modules, architecture]
---
# Module Package Contract

**Status:** Accepted implementation contract
**Introduced:** `0.7.0`
**Authority:** Refines the module boundaries in the product requirements document.

## Ownership boundary

The manager owns installation, compatibility, lifecycle, scheduling, shared
SQLite access, provider access, credentials, global navigation, permissions,
resource policy, and updates. A module owns domain logic, domain validation,
configuration semantics, domain records, and its assigned artifact directory.

Modules never receive an unrestricted shared-database connection or provider
credential. During the in-process migration period, manager-owned composition
adapters construct module repositories and services. The child-process runtime
will replace direct service calls with the versioned loopback protocol in
Increment 8.

## Manifest version 1

`ModuleManifest` is the canonical installed-package description. It contains:

- manifest, module, and module-API versions;
- minimum and maximum-tested core versions;
- module data-schema version;
- stable module ID, display metadata, and storage namespace;
- launch runtime, entry point, and arguments;
- declared task types and work classes;
- one optional session-entry task identifying the module's normal session loop;
- requested permissions with scopes, rationale, and required/optional state;
- manager-compatible UI contribution slots and renderer keys;
- declarative configuration schema.

Module and task IDs use lowercase stable namespaces. Every module task must be
inside its module namespace. The manager rejects missing, undeclared, duplicate,
or core-incompatible task implementations before runtime startup.

## Lifecycle

Installed modules have `enabled`, `paused`, or `not_installed` state. Package
discovery synchronizes manifests without overwriting an explicit user pause.
If a previously known package is absent, its durable record becomes
`not_installed`. Reappearing packages return paused and require an explicit
enable action.

Paused modules retain configuration, data, manifest history, and saved
priority. The manager rejects new task admission for paused modules. Increment
8 will apply the same state to child-process launch and shutdown.

## Storage and migrations

The shared SQLite database remains manager-owned. Core tables use an explicit
`core_` prefix for new module-platform tables. New module tables must use their
manifest storage namespace as a prefix or be reachable only through a
module-scoped manager repository.

Each module receives `%APPDATA%/TWS/Nerve Center/modules/<storage_namespace>`
or the equivalent configured data root. Paths are created by the manager and
never point into the source checkout.

For migration safety, existing Job Scout tables are not renamed in `0.7.0`.
Their ownership is:

- Job Scout: `source_documents`, `career_profiles`, `companies`,
  `discovery_sources`, `source_scans`, `job_openings`, `job_provenance`,
  `search_cache`, `location_preferences`, `company_enrichment`,
  `job_enrichment`, `fit_analyses`, `scoring_settings`, `scoring_rules`,
  `opportunity_scores`, `application_records`, and `application_events`.
- Core manager: `runs`, `run_events`, `core_modules`, `provider_calls`, and
  `schema_state`.

Future migrations must snapshot before changing these tables. Renaming the
legacy Job Scout tables is optional and must not be coupled to process-runtime
work.

## Permissions

Manifest permissions are reviewable declarations, not claims of a complete OS
sandbox. The manager enforces what it can at its APIs and launch boundary and
records declared privileges. Job Scout currently declares configured-domain
public reads, optional public read-only browser automation, and writes to its
assigned storage namespace.

Raw credentials and arbitrary consequential external actions are never module
permissions. Authenticated reads and remote drafts require manager-owned
connectors.

## UI contributions

The manager owns navigation, layout, accessibility, notifications, shared
controls, security, and resource settings. Manifests contribute stable slots
and renderer keys. In MVP, renderer keys resolve only to components explicitly
registered in the trusted manager build. The manager does not load arbitrary
module JavaScript.

Home accepts structured status only. Module dashboards, configuration, records,
review content, and queue-detail renderers live in module-owned tabs within
manager constraints.

## Process runtime

As of `0.8.0`, `managed_python` launch definitions run through the generic
module supervisor. A worker receives only its manager endpoint, scoped runtime
token, module identity, and assigned data directory as process environment.
Run identity, deadline, priority, queue limits, resource policy, configuration,
and checkpoint are delivered through the authenticated loopback protocol.

Workers poll for one manager-authorized assignment at a time and report
heartbeats, activity, backlog, queue pressure, checkpoints, resource
consumption, and completion. Operations are dispatched only through a bridge
registered for that module. The Job Scout bridge temporarily adapts its
existing manager-owned repositories; the worker never receives the shared
database path or provider credentials.

Pause requests stop admission, request graceful worker shutdown, then apply a
bounded terminate/kill fallback. Unexpected process exits fail active work and
surface a failed runtime state. Overdue heartbeats surface a degraded state.

Manager work sessions invoke only `session_entry_task_id`. Additional declared
tasks remain available for explicit workflows and future durable queue
composition; manifest tuple ordering is never used to infer session behavior.

## Durable work delivery

As of `0.10.0`, managed workers submit typed work through their authenticated
runtime route. The manager derives module, run, session, and normalized module
priority from the active assignment; a worker cannot submit those authority
fields itself. Requests carry a work class, stable task identity, payload,
provenance, output contract, requirements, local task priority, retry policy,
and module-scoped idempotency key.

The manager persists a request before acknowledging submission. Every claim
creates a durable attempt. Results remain durable and are delivered at least
once until the owning module acknowledges them. Claimed work is requeued after
manager restart with the interrupted attempt retained. Modules must tolerate
duplicate result delivery and use idempotency keys where repeated execution
would be harmful. Shared SQLite remains manager-only.
