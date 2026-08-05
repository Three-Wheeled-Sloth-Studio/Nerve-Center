# MVP Roadmap

> Product intent and non-negotiable boundaries are defined in `refs/planning/product-requirements-document.md`. This roadmap orders implementation; it does not redefine the product.

## Accepted baseline through 0.8.0

The repository already contains a working local API, durable SQLite foundation, initial scheduling and task concepts, the Job Scout reference workflow, a Tauri/React desktop shell, and Windows packaging/runtime bootstrap.

That baseline proved the application can be packaged and launched. The next work must separate the reusable manager from Job Scout-specific assumptions before adding more domain modules.

## Increment 7: Core and module boundary (implemented)

- Audit current schemas, services, API routes, UI surfaces, and storage for Job Scout entanglement.
- Define the versioned module manifest and compatibility contract.
- Define manager-owned versus module-owned configuration and storage.
- Define module permissions, package shape, UI contribution points, and migration boundaries.
- Move Job Scout-specific behavior behind the same contracts future modules will use.
- Preserve the accepted Windows package and startup-health baseline.

Implemented in `0.7.0`. The manager now validates versioned manifests and
task declarations, persists module lifecycle state, owns module storage roots,
enforces pause state during run admission, and installs Job Scout through a
module bootstrap adapter. The existing Job Scout tables retain their names for
migration safety but have explicit module ownership. Process isolation and the
loopback runtime protocol begin in Increment 8.

## Increment 8: Module process runtime (implemented)

- Launch enabled modules as supervised child processes.
- Add scoped runtime tokens and a versioned loopback HTTP/event protocol.
- Provide run identity, window end, priority, queue limits, resource policy, and assigned data directory at launch.
- Add module heartbeat, lifecycle state, activity, backlog, queue-pressure, and degraded-state reporting.
- Support Enabled, Paused, and Not Installed lifecycle states.
- Add manager-rendered compact module cards and manager-owned module tabs.

Implemented in `0.8.0`. Job Scout task orchestration now runs in a supervised
managed-Python child process. The manager issues a per-launch scoped token,
serves a versioned loopback protocol, delegates only registered module
operations, and retains exclusive ownership of shared persistence and resource
accounting. Runtime cards report process state, activity, heartbeat, backlog,
queue pressure, and completed work. Pause requests perform graceful shutdown
with bounded forced termination.

## Increment 9: Session scheduler and wind-down

- Make manager work sessions the primary scheduling unit.
- Support duration-based, fixed-time, and recurring wall-clock windows.
- Launch all enabled modules for a session.
- Add Open, Constrained, Draining, and Closed admission phases.
- Tell modules when remaining time and queue estimates no longer justify discovering new LLM-dependent work.
- Complete queued LLM work during normal graceful wind-down.
- Add explicit Emergency Stop.
- Restore active sessions after application or machine restart using the original wall-clock end.

## Increment 10: Durable shared work queue

- Add generic deterministic, network, LLM, human-review, and composite work classifications.
- Persist typed requests before acknowledgement.
- Add durable attempts, results, acknowledgements, redelivery, and idempotency keys.
- Enforce global and per-module soft and hard queue limits.
- Estimate each module’s next-request wait and queue-clear time.
- Normalize enabled-module priorities to exactly 100 points.
- Order LLM work using module priority, request age, task priority, model suitability, and model-switch cost.
- Add progressively disclosed queue inspection, retry, cancellation, and reprioritization controls.

## Increment 11: Provider-neutral LLM manager

- Move every LLM invocation behind manager-owned provider adapters.
- Prohibit direct provider calls from modules.
- Define model-blind task requirements and structured result contracts.
- Add Ollama discovery and invocation as the first local runtime.
- Add capability, hardware-fit, performance, failure, retry, validation, and acceptance observations by task type.
- Add policy-driven retry and quality-tier escalation without exposing model names to modules.
- Preserve a cloud-provider abstraction with local-only as the default and bring-your-own credentials when enabled later.

## Increment 12: Model Lab

- Add a manager-owned, toggleable Model Lab subsystem outside module priority.
- Maintain a model catalog seeded by Ollama metadata, compatibility data, and relevant public benchmarks or leaderboards.
- Add policy-constrained automatic model installation and separate opt-in automatic removal.
- Retain eligible real requests as a local benchmark corpus by default, with user and module opt-out.
- Reserve a configurable 5–10% exploration ceiling during contention while freely using otherwise idle compute.
- Add explicit exploration sessions such as “Explore models for four hours.”
- Reuse historical real requests for comparison.
- Add simple blinded pairwise A/B review using a Likert preference scale.

## Increment 13: Attention, safety, and connectors

- Add manager-owned Attention and Review queues.
- Let modules supply domain context, allowed dispositions, validation, and downstream meaning.
- Block only dependent workflow branches by default.
- Add morning summaries for completed, blocked, failed, degraded, and comparison work.
- Add install-time module permission review.
- Define public-read, authenticated-read, local-write, external-draft, and prohibited external-action classes.
- Allow authenticated read and non-public remote drafts only through explicit manager-owned connectors.
- Keep browser automation read-only for the initial product; defer form filling.

## Increment 14: Resource profiles, durability, and updates

- Add global resource defaults and per-session overrides for CPU, memory, GPU/VRAM, concurrency, queue depth, storage, network, exploration, and optional cloud spend.
- Add named reusable profiles such as Quiet, Balanced, Overnight, and Model Exploration.
- Add lightweight daily backups and pre-migration snapshots.
- Add compatibility-aware independent core and module updates.
- Support one global Stable or Development channel.
- Stage updates, drain active work, migrate, health-check, and roll back binaries when necessary.
- Apply staged updates on restart while preserving user and module data.

## Reference-module continuation

Job Scout remains the first reference module and should continue to improve, but its domain roadmap is subordinate to the core boundary:

- resume and evidence-profile management remain module configuration;
- source policies and connectors remain module capabilities;
- discovery, normalization, scoring, application tracking, and review remain module-owned;
- Job Scout requests LLM work through the generic manager contract;
- Job Scout may not add domain-specific assumptions to core manager schemas or navigation.

A second substantially different module should be introduced early enough to validate that the contracts are truly generic rather than Job Scout with the labels filed off.

## Deferred increments

- Code signing and broad public distribution.
- Cross-platform packaging.
- Standalone or externally callable LLM router.
- Third-party and user-authored modules.
- Untrusted-module sandboxing and marketplace.
- Per-module update channels.
- Advanced staggered module schedules.
- Machine-idle, battery, metered-network, and active-user-sensitive scheduling.
- Automated form filling.
- Remote administration and headless workers.
- Multi-user or team support.
- Cloud synchronization and mobile access.

## Permanent non-goals

- Automated job applications.
- Automated outreach or email sending.
- Automated book, social-media, or website publishing.
- Purchases, acceptance of legal terms, or unattended external-account changes.
- Any module bypass of the manager-owned LLM boundary.
- Domain-specific reference-module logic embedded in the core manager.
- User data or credentials stored in the public source repository.
