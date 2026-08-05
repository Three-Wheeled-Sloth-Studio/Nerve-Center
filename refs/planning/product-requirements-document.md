# Nerve Center Product Requirements Document

**Status:** Approved product baseline  
**Stamped:** 2026-08-05  
**Target:** MVP and near-roadmap architecture  
**Audience:** Product, design, engineering, and module authors  
**Authority:** This document is the product-definition source of truth. More detailed contracts may refine implementation, but may not weaken the boundaries established here without an explicit product decision.

## 1. Executive summary

Nerve Center is a single-user, local-first orchestration runtime for long-horizon unattended work. It lets a technically comfortable user authorize bounded periods in which locally installed modules can perform useful work, mostly independently, while sharing manager-owned scheduling, resources, durable state, model infrastructure, review surfaces, and update services.

The core product is the manager and orchestrator. Job Scout, Asset Forge, Wordsmith, and future domain workflows are modules. They may remain in this repository or move to separate repositories, but they must remain cleanly separable from the core product.

Nerve Center is designed around work streams with no natural endpoint: there is always another source to monitor, asset to process, opportunity to inspect, or draft to improve. Users therefore authorize wall-clock run windows rather than asking the system to complete a finite job. Modules use those windows to perform deterministic and network work in their own supervised processes and request occasional LLM assistance through the manager.

The manager owns the entire LLM boundary. Modules describe the work they need; they do not know which models or providers exist and may never call them directly. The manager selects, schedules, loads, evaluates, and improves its use of models while respecting user policy, resource limits, privacy, module priority, and queue age.

Nerve Center may analyze, prepare, draft, transform, package, and stage work. It does not take unattended consequential external action. A human must remain in the loop before submission, publication, communication, purchase, account change, or any comparable last-mile action.

## 2. Product thesis

Useful personal automation is rarely one clean prompt with one clean answer. The valuable work is often long-running, repetitive, partly deterministic, and only occasionally improved by an LLM. Running several such workflows independently creates duplicated schedulers, competing model processes, inconsistent storage, resource contention, fragile recovery, and no unified understanding of what happened overnight.

Nerve Center provides the shared operating layer:

- authorize when unattended work may run;
- supervise independent modules;
- allocate constrained resources;
- own and optimize model access;
- preserve work and results across failures and restarts;
- surface compact operational status and human-review needs;
- keep domain logic inside modules rather than welding it into the manager.

Internally, Nerve Center is a local agent operating system. Externally, it should be presented as a modular AI work manager rather than making broader operating-system claims.

## 3. Initial user and use context

The initial user is a technically comfortable individual running Nerve Center on a Windows desktop or workstation. They want useful work to continue during periods when they are not actively using the machine, especially overnight.

The primary timing question is not “How many compute hours do I want?” It is “During which wall-clock hours may Nerve Center use this machine?” Wall clock is therefore authoritative for run windows, sleep, restart, and missed-session behavior.

MVP explicitly targets:

- one user;
- one local machine;
- Windows desktop operation;
- local durable storage;
- local models as the default;
- first-party modules;
- unattended preparation and analysis with human review before external action.

The architecture should avoid unnecessarily blocking future support for other operating systems, headless operation, remote workers, third-party modules, multiple users, or a standalone routing service, but none are MVP requirements.

## 4. Product boundaries

### 4.1 Core manager responsibilities

The manager owns:

- work-session scheduling and wall-clock run windows;
- module discovery, installation, enablement, pausing, launch, supervision, upgrade, removal, and compatibility checks;
- normalized module priority allocation;
- global and per-session resource limits;
- durable task admission, queueing, ordering, retry, cancellation, delivery, and history;
- the complete LLM and provider boundary;
- model discovery, installation, selection, loading, unloading, benchmarking, and performance instrumentation;
- shared durable storage services and manager-assigned module data areas;
- unified attention, review, status, diagnostics, and notification surfaces;
- application and module update coordination;
- core navigation, dashboard, design system, and security framework;
- explicit connectors for authenticated or remote draft operations.

### 4.2 Module responsibilities

A module owns:

- its domain-specific business logic;
- its configuration schema and configuration UI;
- its deterministic and network work loops;
- work discovery, domain checkpoints, and domain validation;
- deciding when LLM uplift is needed;
- describing LLM work through typed, model-blind requests;
- interpreting returned results;
- domain-specific records, result views, and review semantics;
- monitoring its manager-reported queue pressure and throttling itself appropriately;
- stopping discovery when its run authorization is ending or the manager enters drain mode;
- reporting health, activity, backlog, alerts, and lifecycle state through the manager contract.

A module does not own scheduling, provider credentials, model selection, model lifecycle, global navigation, global notifications, update policy, or shared resource arbitration.

### 4.3 Reference modules are not the product

Job Scout is the first reference module. Its resume handling, source rules, scoring, job records, application workflow, and related configuration belong to Job Scout. They must not become assumptions embedded in core manager schemas or navigation.

The same rule applies to future modules such as Asset Forge or Wordsmith. Core contracts must remain generic, even when a reference module is the only current consumer.

## 5. Non-negotiable design principles

### 5.1 The manager exclusively owns model access

Modules may never call Ollama, a cloud LLM API, an OpenAI-compatible endpoint, or any other model provider directly. There is no advanced permission or escape hatch for normal module execution.

Modules state what work is required. The manager decides who can do it, when it should run, and whether a result should be retried or escalated. This is essential to prevent provider races, duplicate model loading, memory contention, uncontrolled cloud use, and inconsistent performance learning.

### 5.2 Local-first and provider-neutral

Local execution is the default product shape. Ollama is the first supported local runtime, not a permanent architectural dependency.

The manager must expose provider-neutral contracts capable of supporting additional local runtimes and user-configured cloud providers. Cloud credentials are bring-your-own and remain manager-owned. Cloud routing is prohibited by default and requires explicit user policy.

### 5.3 Durable by default

Schedules, tasks, attempts, results, reviews, model observations, module state, and migrations must survive ordinary crashes, application restarts, and machine restarts.

User data belongs in operating-system application-data locations, not the source checkout. SQLite is the shared standard store, with manager-assigned isolated directories available for large or specialized module artifacts.

### 5.4 Human in the loop before external action

Nerve Center may prepare the last mile but does not cross it unattended.

It may generate application files, publishing packages, drafts, metadata, or a link to the correct final workflow. It may not autonomously submit an application, send a message, publish content, make a purchase, accept terms, change an external account, or commit the user to an external representation or transaction.

This is a product invariant, not a default setting that modules may request permission to disable.

### 5.5 Progressive disclosure

The default experience should explain what is running, what needs attention, and what happened without requiring the user to operate a raw task system. Advanced queue, execution, model, and diagnostic detail remains available for inspection and intervention.

### 5.6 First-party trust without architectural entanglement

Initial modules are trusted first-party packages. They still use manifests, permissions, process isolation, versioned contracts, and assigned storage. The product should leave a path toward third-party modules without claiming to provide a secure untrusted-plugin sandbox in MVP.

## 6. Work sessions and scheduling

### 6.1 Primary mental model

Users schedule manager work sessions, not independent module schedulers. A session authorizes Nerve Center to work during a wall-clock window and applies a resource policy and module priority allocation.

Examples:

- run for one hour starting now;
- run from 6:00 PM until 8:00 AM;
- run nightly during a recurring overnight window;
- run all enabled modules for four hours using an exploration-heavy resource profile.

If the user wants only one module to participate, they pause the others. A future module-level “Run this module for one hour” command or advanced staggered scheduler may create a targeted session, but is not required for the near roadmap.

“Run now” always requires a duration or end time because supported work streams usually have no natural endpoint.

### 6.2 Session behavior

At session start, the manager:

1. resolves the authorized start and end time;
2. selects all enabled modules;
3. launches each eligible module as a supervised child process;
4. provides the run identity, window, queue policy, resource policy, priority allocation, assigned data directory, and manager connection details;
5. tracks heartbeats, activity, queue state, and resource use.

Modules may perform deterministic and network work concurrently within policy. They submit occasional LLM requests and may sleep themselves when idle, blocked, or saturated.

### 6.3 Admission phases

The manager continuously considers remaining authorized time, estimated queue-clear time, estimated wait for a new request, task duration history, and current model-switch cost. A session moves through four admission phases:

- **Open:** normal work discovery and request admission.
- **Constrained:** new work is accepted selectively based on estimated value and completion time.
- **Draining:** modules stop discovering work likely to require LLM processing; no new LLM requests are accepted; queued and in-flight requests continue.
- **Closed:** no module work remains authorized.

The manager communicates both the phase and useful estimates to modules. Rejections use structured reasons such as `run_window_draining`, `estimated_completion_exceeds_window`, `module_queue_limit`, `global_queue_limit`, or `resource_budget_exhausted`.

MVP should begin telling modules to stop producing new work when queued work is likely to consume the remaining window.

### 6.4 Window end

Normal session completion uses graceful wind-down:

- stop admitting new work;
- tell modules to stop discovery;
- allow current deterministic operations to checkpoint;
- let queued and in-flight LLM requests run their course;
- persist and deliver results;
- terminate modules after they report stopped or exceed a bounded shutdown timeout.

Pending results remain durable after the module stops. They are redelivered during the next eligible run until acknowledged.

### 6.5 Emergency Stop

The product must provide a prominent, explicit Emergency Stop control.

Emergency Stop:

- rejects new work immediately;
- cancels queued requests;
- attempts to cancel active provider calls;
- terminates module processes after a short timeout;
- preserves durable state and records incomplete work.

Emergency Stop is a user action, not the normal way a window closes.

### 6.6 Sleep, restart, and missed sessions

Wall clock remains authoritative:

- sleep time counts against the authorized window;
- if the machine wakes while the window remains open, the manager resumes eligible work;
- lost sleep or downtime is not automatically added to the end;
- after an application or machine restart during an active window, the manager restores the session from durable state and resumes until the original end time;
- missed recurring windows are recorded but not replayed unless a future schedule explicitly enables catch-up.

Machine-idle detection and active-user-sensitive throttling are deferred enhancements.

## 7. Module runtime and lifecycle

### 7.1 Process isolation

Modules run as manager-launched child processes. A failed, blocked, or misbehaving module must not crash the manager or another module.

The initial communication boundary is a versioned loopback HTTP API with an event channel such as WebSocket or server-sent events. Strict OS-specific IPC and sandboxing are unnecessary for MVP.

The manager issues a scoped runtime token and launch context including:

- manager endpoint;
- module ID and version;
- module run ID;
- authorized window end;
- assigned data directory;
- queue and resource policy references;
- cancellation and shutdown semantics.

Modules should not select their own listening ports unless a future capability explicitly requires it.

### 7.2 Lifecycle states

Installed modules have three user-visible lifecycle states:

- **Enabled:** participates in scheduled sessions.
- **Paused:** retains configuration, data, and saved priority but does not start automatically.
- **Not Installed:** package is absent.

While a module is paused, its saved priority is remembered but its active allocation is zero. Enabled modules are temporarily renormalized to a total of 100 points. Resuming restores the saved allocation.

### 7.3 Runtime health contract

A running module reports one of:

- `starting`
- `working`
- `idle`
- `throttled`
- `waiting_for_llm`
- `waiting_for_human`
- `stopping`
- `stopped`
- `degraded`
- `failed`

Heartbeat payloads include, where applicable:

- one-line current activity;
- last heartbeat time;
- work items processed;
- deterministic backlog estimate;
- pending LLM request count;
- estimated next-request wait;
- estimated time to clear the module queue;
- current resource use;
- reason for sleeping, throttling, degradation, or blockage.

The manager may terminate and restart an unresponsive module after module-appropriate heartbeat allowances.

### 7.4 Package contract

A module bundle contains:

- a versioned manifest;
- process executable or managed-runtime launch definition;
- UI assets and metadata;
- configuration schema;
- permission declarations;
- task-type declarations;
- data migrations;
- compatibility metadata;
- health metadata;
- icons and optional manager-compatible renderers.

Bundled and independently downloaded first-party modules use the same package and lifecycle contract. MVP may use a shared manager-controlled Python runtime. The contract must permit self-contained executables later.

### 7.5 Lifecycle operations

The manager owns:

- install;
- enable and pause;
- configure;
- prioritize;
- upgrade;
- compatibility checks;
- health and degraded-state reporting;
- export and reset flows;
- removal.

Binary rollback and data-recovery support are required around updates. A full module marketplace and user-authored module tooling are deferred.

## 8. Work and task contracts

### 8.1 Work classification

The manager recognizes at least these work classes:

- local deterministic work;
- network work;
- LLM work;
- human-review work;
- composite workflow.

The manager schedules sessions and shared resources. Modules retain ownership of their internal deterministic workflow and checkpoints.

### 8.2 Model-blind LLM request

A module submits a typed request describing the work, never a model name or provider preference.

A request includes fields such as:

- stable task identity, for example `job_scout.evaluate_fit`;
- input payload and provenance references;
- output schema;
- modality requirements;
- context-size requirement;
- structured-output requirement;
- tool-use requirement;
- privacy classification;
- quality tier;
- latency sensitivity;
- reasoning intensity;
- creativity-versus-factuality profile;
- expected output size;
- fallback policy;
- deterministic validation availability;
- module-local task priority;
- idempotency or deduplication key;
- retry and review hints.

The exact task identity is the primary unit for empirical model learning. Broader capability categories provide starting priors for new task types.

### 8.3 Validation split

The manager validates:

- provider completion;
- response decoding;
- required output schema and fields;
- size and type limits;
- retry policy and budget;
- duplicate, attempt, and delivery state.

The module validates:

- domain correctness;
- deterministic domain checks;
- whether the result is useful enough to continue;
- whether human review is required;
- the downstream meaning of acceptance, rejection, warning, or blockage.

A module may reject a result with structured reasons or request a higher quality tier, but it may not ask for a named model. The manager decides whether another attempt fits policy and which model receives it.

### 8.4 Delivery guarantees

The task and result protocol is durable and at-least-once:

- every request has a durable unique ID;
- the manager persists a request before acknowledging it;
- modules provide idempotency or deduplication keys where repeat work would be harmful;
- results remain durable until acknowledged;
- unacknowledged results are redelivered after restart;
- every attempt and final disposition is recorded;
- modules must safely handle duplicate delivery.

Exactly-once execution is not promised.

## 9. Queueing, priority, and backpressure

### 9.1 Normalized module priority

Enabled modules share exactly 100 priority points. The user should eventually be able to adjust the allocation through both exact numeric controls and a draggable pie-chart boundary visualization.

A newly enabled module receives a small default share and reduces other active allocations proportionally. Users may lock selected allocations while editing the remainder.

System work is outside the module 100-point pool. Updates, health checks, migrations, backups, and manager-owned model research do not masquerade as another module.

### 9.2 Execution order

LLM request ordering should consider:

- module priority;
- request age;
- module-local task priority;
- model suitability;
- currently loaded model;
- estimated load and unload cost;
- expected task duration;
- resource availability.

The initial policy should behave like a priority-age-model score: keep using the loaded model while the benefit is reasonable, but switch when accumulated priority and age outweigh model-switch cost. Batching must not starve lower-throughput modules indefinitely.

True deadlines may remain in the contract, but are not central to MVP use cases.

### 9.3 Queue visibility and backpressure

The manager reports to each module:

- current module queue depth;
- global queue pressure relevant to that module;
- estimated wait for the module’s next submitted request;
- estimated time to clear the module’s existing queue;
- current admission phase;
- soft and hard queue limits.

The manager enforces hard limits and may defer or reject work. Modules are responsible for respecting soft thresholds and sleeping or slowing discovery rather than flooding the queue.

The user sees the same estimates in manager-rendered status and queue surfaces.

## 10. Models, providers, and empirical routing

### 10.1 Provider policy

The manager is local-first and provider-neutral:

- Ollama is the first supported runtime;
- modules have no provider awareness;
- cloud providers require user-supplied credentials;
- secrets use the operating-system credential store, not plaintext SQLite;
- local-only is the default routing policy;
- cloud use requires explicit task-class or privacy policy;
- global and provider-specific spending limits are supported when cloud providers are enabled;
- model exploration has a separate cloud-spend budget and cannot silently spend cloud money.

### 10.2 Suitability registry

The manager maintains a capability and observation registry including:

- model and provider identity;
- installed state and version;
- context and modality support;
- structured-output and tool-use reliability;
- observed task suitability;
- speed, load time, memory, and VRAM use;
- failure and retry rates;
- hardware and runtime context;
- module acceptance and deterministic validation outcomes;
- optional user ratings;
- estimated or actual cloud cost.

Initial model selection may resemble manager-controlled automatic routing. Users may later set policies and overrides, but modules remain model-blind.

### 10.3 Model discovery and installation

The manager discovers locally installed Ollama models and maintains a model catalog informed by:

- Ollama availability and quantizations;
- model size and hardware fit;
- context window and capabilities;
- license and source;
- release age and runtime compatibility;
- relevant public benchmarks and leaderboards;
- local empirical performance.

External descriptions and leaderboards seed candidate selection; they do not determine the winner. Local task performance is authoritative for local routing.

Auto-install is configurable and constrained by:

- maximum model storage;
- minimum free disk space;
- maximum model size;
- allowed sources or families;
- hardware compatibility;
- active-work and network policy.

The normal user default is approval-oriented. Aggressive testing may enable auto-install within storage limits so the manager can explore the model space empirically.

Automatic removal is a separate permission and is off by default. The manager reports last use, task coverage, proven unique value, and redundant alternatives. Users may pin models. Models under active evaluation may not be removed.

### 10.4 Model Lab

Model research is a manager-owned core subsystem, surfaced as a toggleable **Model Lab**, not a normal module. It may be scheduled and budgeted, but it remains outside module priority because model knowledge and routing are core responsibilities.

Model Lab balances production use and exploration:

- a configurable ceiling, initially suggested at 5–10% of compute under contention;
- free use of otherwise idle compute;
- immediate yield to production work that would otherwise wait;
- explicit sessions such as “Explore models for four hours”;
- reuse of past real requests for realistic local benchmarking;
- bounded comparison shopping when the live request queue is light.

### 10.5 Benchmark corpus

Local benchmark retention is enabled by default for local models, with user and module opt-out.

The benchmark corpus may retain:

- task identity and capability requirements;
- replayable input payload or local benchmark copy;
- output schema;
- deterministic validation results;
- previously accepted outputs;
- human ratings;
- privacy and provider-reuse restrictions;
- hardware and runtime context.

Credentials, unstable external references, and tasks marked ephemeral or non-replayable must not be retained for replay. Cloud benchmarking follows the same explicit privacy and budget rules as production cloud use.

### 10.6 Creative comparison review

The first comparison workflow should remain simple:

- blinded pairwise outputs;
- randomized A/B order;
- a Likert-style preference scale from strong A through equal to strong B;
- options for both good, both unacceptable, cannot compare, and skip;
- optional lightweight reason tags;
- task-specific quality learning rather than one universal model score.

Live comparison results may allow the user to select the accepted production result. Replayed benchmark comparisons collect ratings only.

Numeric model-quality scoring is a desirable goal but is not required for MVP. Initial evidence may combine schema validity, deterministic checks, module acceptance, retries, speed, and optional user review.

## 11. Human attention and review

The manager owns review infrastructure. Modules own review meaning.

The manager provides:

- a unified Attention and Review surface;
- durable review-item storage;
- notifications and counts;
- generic open, defer, skip, resolve, and comparison interactions;
- audit history;
- reliable return of review decisions to the originating module.

A module provides:

- review content and domain context;
- allowed dispositions;
- domain validation;
- the downstream meaning of each disposition;
- optional reason tags or specialized fields compatible with the manager design system.

A review requirement normally blocks only the dependent item or workflow branch. Whole-module blocking must be explicitly declared with a reason. Independent work should continue.

Review items may accumulate overnight. Human review does not consume the run window. Blocked items remain durable for a later session. The manager may present a morning summary of completed work, pending review, failures, degradation, and model comparisons without persistent nagging while the user is away.

## 12. External systems and permissions

### 12.1 Permission framework

Every module manifest declares requested capabilities, including:

- network access and allowed domains;
- read or write access outside the assigned data directory;
- browser automation;
- clipboard, notification, process, or device access;
- credential references;
- remote draft eligibility;
- cloud-eligible data classifications.

Installation presents a permission review even for first-party modules. MVP enforcement may be partial because modules are trusted child processes, but undeclared privileged operations should be rejected where the manager can enforce them.

### 12.2 External interaction classes

The permission model distinguishes:

- **Public read:** retrieve public pages, feeds, or APIs.
- **Authenticated read:** access explicitly authorized external data.
- **Local write:** modify local files or module-owned state.
- **External draft:** create a non-public, non-sent remote draft through a manager-owned connector.
- **Consequential external action:** prohibited for unattended execution.

Remote drafts are allowed only through explicit manager-owned connectors whose operation is known to be non-consequential. Modules do not receive raw credentials or decide through arbitrary browser automation that a remote action is “only a draft.”

### 12.3 Browser automation

Browser automation is a privileged declared capability. Initial scope permits read-only navigation and extraction, including authenticated read through scoped manager-owned session or credential references.

Automated form filling is deferred. Submission controls remain out of scope. The manager logs authenticated operations without exposing credentials or sensitive page bodies.

Future social-media or WordPress auto-publishing belongs in another product, not Nerve Center.

## 13. Storage, backup, and migration

### 13.1 Storage shape

The manager maintains a shared durable SQLite database with explicit core and module namespaces. Modules may also use isolated manager-assigned directories for large artifacts or specialized stores.

Core storage includes:

- modules and compatibility state;
- schedules and sessions;
- task requests, attempts, results, and acknowledgements;
- queue and execution history;
- providers, models, observations, and benchmark metadata;
- updates, migrations, backups, alerts, and reviews.

Modules own their domain tables or namespaces and assigned directories. One module may not modify another module’s data.

### 13.2 Backups

Nerve Center performs:

- an automatic snapshot before every core or module migration;
- lightweight routine daily snapshots;
- configurable retention by count and disk ceiling;
- backup of module configuration and manifests;
- health checks after migration;
- explicit recovery flows rather than silent destructive rollback.

Support bundles exclude sensitive payloads by default.

### 13.3 Migration and rollback

Core and modules declare data schema versions and migrations. A module may migrate only its namespace and assigned directory.

Binary rollback is permitted when startup or health checks fail. Migrated user data is not rolled back unless a supported reverse migration exists or the user explicitly restores a backup.

## 14. Updates and release channels

Core and modules have independent versions and may update independently, but the manager coordinates compatibility and safe sequencing.

MVP supports one global update channel:

- **Stable:** versioned releases from `main`.
- **Development:** pre-release builds from `dev` for active testing.

Development builds still require backups, migrations, compatibility checks, and health validation.

Compatibility metadata includes:

- core version;
- module version;
- module API version;
- minimum core version;
- maximum tested core version;
- data schema version.

The manager:

- checks a release manifest or trusted release source;
- stages updates in the background;
- waits for active work to drain;
- applies core and module updates in a compatible order;
- runs migrations and health checks;
- blocks incompatible modules rather than launching them;
- preserves application and module data;
- applies staged updates on restart when appropriate.

Per-module update channels, signed public distribution, and broader release pipelines are later concerns. Dev/main segmentation is sufficient initially.

## 15. Resource policy

The manager supports global defaults and per-session overrides for:

- CPU use;
- memory use;
- GPU and VRAM use;
- maximum concurrent deterministic workers;
- maximum concurrent network operations;
- global and per-module pending LLM requests;
- model storage;
- network restrictions;
- cloud spending when enabled;
- model-exploration ceiling.

Named reusable profiles are a near-roadmap usability layer, with likely presets such as Quiet, Balanced, Overnight, and Model Exploration. MVP may begin with one global default plus per-session overrides.

Machine-idle scheduling, metered-network awareness, battery-sensitive behavior, and active-user throttling are deferred.

## 16. User experience

### 16.1 Core navigation

Initial top-level navigation:

- Home
- Schedule
- Queue
- Models
- Attention
- module tabs
- Settings

History and diagnostics may initially live within Queue, Models, and Settings.

### 16.2 Home

Home remains intentionally restrained. It includes:

- current session and time remaining;
- compact manager-rendered cards for active modules;
- global queue and resource summary;
- attention-required alerts;
- update or degraded-system status.

A module may write only structured status and alert values into its reserved dashboard card. It may not inject arbitrary HTML, charts, controls, or promotional content into Home.

The initial module card may show:

- name and icon;
- lifecycle state;
- one-line current activity;
- time remaining;
- compact deterministic backlog signal;
- LLM queue depth;
- estimated next-result wait;
- one alert indicator;
- click-through to the module tab.

This may be simplified further after usability testing.

### 16.3 Module UI

Modules may provide:

- a module dashboard;
- configuration panels;
- domain records and result views;
- module commands;
- review content;
- manager-compatible queue-detail renderers.

The manager owns tabbing, navigation, layout constraints, shared controls, accessibility, notifications, queue policy, security and resource settings, and the overall visual design system.

### 16.4 Advanced operations

The queue and model surfaces use progressive disclosure. Advanced users may inspect, reprioritize, cancel, retry, compare, and diagnose individual work without making raw queue operation the default product experience.

## 17. MVP product requirements

MVP is complete only when the product demonstrates the following manager-owned behavior with at least one cleanly separated reference module:

1. The user can define a bounded wall-clock session and recurring run window.
2. Enabled modules launch as supervised child processes and stop through graceful wind-down.
3. Modules receive session timing, priority, queue, resource, and data-directory context.
4. Modules report lifecycle state, heartbeat, activity, backlog, queue depth, and wait estimates.
5. Modules can perform independent deterministic or network work during the session.
6. Modules submit durable, typed, model-blind LLM requests.
7. The manager exclusively selects and invokes the provider and model.
8. Queue order considers normalized module priority, request age, model suitability, and model-switch cost.
9. Soft and hard queue limits prevent unbounded module request production.
10. The manager enters constrained and draining phases as the session closes.
11. Already queued LLM work completes during normal wind-down and results remain durable.
12. The task protocol survives process and application restart through at-least-once delivery and acknowledgement.
13. Ollama models are discovered and routed through a provider-neutral contract.
14. Model timing, validity, failure, retry, and acceptance evidence is recorded by task type.
15. Auto-install can be enabled within storage and hardware limits.
16. Model Lab can replay eligible real requests and perform bounded pairwise comparison work.
17. The manager exposes unified Attention and Review surfaces.
18. The manager enforces the human-before-external-action invariant.
19. Core and modules store data locally, back up routinely, and snapshot before migration.
20. Core and module updates are compatibility-aware and support global stable/dev channels.
21. Home, Schedule, Queue, Models, Attention, module tabs, and Settings follow manager-owned UX boundaries.
22. The product provides both graceful stop and an explicit Emergency Stop.

## 18. Near-roadmap sequence

The exact issue sequence may change, but implementation should move in this dependency order:

### Foundation alignment

- separate current Job Scout assumptions from core contracts;
- define module manifest, package, permission, and process contracts;
- define sessions, normalized priorities, queue estimates, and resource policy;
- preserve existing Windows bootstrap and package smoke baseline.

### Module runtime

- child-process launcher and versioned local protocol;
- heartbeat and lifecycle supervision;
- enabled/paused lifecycle;
- assigned storage and module migration boundaries;
- compact manager-rendered module cards and module tabs.

### Session scheduler

- global sessions and recurring wall-clock windows;
- Open, Constrained, Draining, and Closed admission phases;
- graceful wind-down and Emergency Stop;
- restart and sleep recovery using wall clock;
- global defaults and per-session resource overrides.

### Shared work queue

- durable typed requests and results;
- at-least-once delivery and acknowledgements;
- module soft and hard limits;
- queue-depth and wait-time estimation;
- normalized priority-age-model ordering;
- advanced queue inspection and intervention.

### Provider-neutral LLM manager

- model-blind task contracts;
- Ollama discovery and invocation;
- model capability registry;
- performance instrumentation;
- policy-based retries and escalation;
- local-first cloud-provider abstraction without enabling automatic cloud use.

### Model Lab

- model catalog and external benchmark metadata;
- policy-constrained auto-install;
- local benchmark corpus;
- 5–10% exploration ceiling and idle-compute use;
- explicit exploration sessions;
- blinded pairwise review.

### Review, safety, and durability

- manager-owned Attention and Review queues;
- module-owned review semantics;
- explicit connector boundary for authenticated read and remote drafts;
- permission review;
- daily backups, migration snapshots, and recovery;
- compatibility-aware independent module updates;
- stable/dev release channels.

## 19. Success measures

MVP success is primarily operational, not a count of domain features.

The product should demonstrate:

- a user can authorize an overnight session and understand what happened the next morning;
- multiple modules can make progress without duplicating schedulers or contending directly for models;
- no module can bypass manager-owned LLM policy;
- application or module restarts do not silently lose acknowledged work;
- queue pressure causes graceful module throttling rather than runaway accumulation;
- model routing improves from task-specific local evidence;
- model comparison uses bounded spare compute and produces reviewable evidence;
- local data, credentials, and external-action boundaries remain clear;
- a reference module can be removed or moved to another repository without dismantling the manager.

Candidate quantitative measures include:

- successful session completion rate;
- recoverable versus lost tasks after forced restart;
- queue estimate calibration;
- model load/unload time avoided through batching;
- task completion latency by task type;
- schema-valid and module-accepted result rate;
- retry and failure rate;
- user-reviewed model preference evidence;
- backup and migration recovery success;
- number of core changes required to add a second independent module.

Numeric quality scoring is desirable but not required for the first MVP acceptance gate.

## 20. Permanent non-goals and deferred directions

### 20.1 Permanent product boundaries

Nerve Center is not intended to:

- take unattended consequential external action;
- auto-submit applications;
- auto-send outreach or email;
- auto-publish books, social posts, or websites;
- make purchases or accept legal terms;
- silently modify external accounts;
- allow modules to bypass the manager’s LLM boundary;
- treat a reference module’s domain schema as a core schema;
- store user data in the source repository.

A separate product may use Nerve Center outputs to perform publishing or other automated external action under a different safety and permission model.

### 20.2 Deferred product surfaces

The following are intentionally deferred without being permanently prohibited:

- standalone or externally callable LLM router;
- third-party or user-authored modules;
- true untrusted-module sandboxing;
- module marketplace;
- per-module update channels;
- advanced staggered module schedules;
- machine-idle and active-user-aware scheduling;
- automated form filling;
- remote administration;
- headless or server deployment;
- multi-user or team operation;
- cross-platform packaging;
- cloud synchronization;
- mobile access.

A future LLM-routing surface must remain manager-owned and must not create a back door for modules to manage providers independently.

## 21. Related planning documents

This PRD establishes product intent and boundaries. Supporting documents may provide narrower implementation detail:

- `refs/planning/product-vision-and-architecture.md`
- `refs/planning/mvp-roadmap.md`
- `refs/planning/data-and-privacy-boundary.md`
- `refs/planning/decision-register.md`
- module-specific contracts such as Job Scout scoring and source behavior
- engineering contracts and handoffs under `refs/engineering` and `refs/handoffs`

Where older language conflicts with this PRD, this PRD controls until the older document is aligned.