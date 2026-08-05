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

## Process handoff

The launch definition is descriptive in `0.7.0`; Job Scout uses the
`in_process_adapter` runtime while its existing behavior is migrated. Increment
8 must add:

1. supervised child-process launch;
2. scoped runtime tokens;
3. versioned loopback HTTP and event contracts;
4. assigned run, window, priority, queue, resource, and storage context;
5. heartbeat and lifecycle supervision;
6. graceful shutdown and bounded forced termination.
