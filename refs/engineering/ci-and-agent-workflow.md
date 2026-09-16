---
type: Engineering Workflow
title: CI and Coding-Agent Workflow
description: Nerve Center CI signal discipline and coding-agent operating rules.
status: stable
tags: [nerve-center, engineering, ci, agents]
---
# CI and Coding-Agent Workflow

## Purpose

Nerve Center treats CI notifications as operational signals, not as a running transcript of development. A failed workflow should mean that a reviewable checkpoint is broken or that an accepted branch regressed. It should not mean that an agent saved another intermediate commit while diagnosing a known failure.

The canonical cross-project principle is maintained in `Three-Wheeled-Sloth-Studio/TWS-Design-Principles` under `engineering/CI-Signal-Discipline.md`. This document records the Nerve Center implementation and project-specific operating rules.

## Workflow behavior

The main CI workflow follows these rules:

- Pushes to `main` and `dev` run full validation.
- Draft pull requests do not run the full validation jobs automatically.
- Marking a pull request ready for review triggers full validation.
- `workflow_dispatch` remains available for an intentional manual checkpoint while a pull request is still a draft.
- A newer run for the same pull request or branch cancels the older in-progress run.
- The expensive Tauri Rust check waits for Python and React validation to pass.

This keeps accepted branches protected while preventing one email per diagnostic commit during active development.

## Coding-agent operating rules

### Return to the integration branch after merge

`dev` is Nerve Center's active integration and development branch. Topic branches may be used for reviewable pull requests, but after a topic branch is merged, switch the active working checkout to `dev`, update it to the accepted merge commit, and continue work from `dev`. Do not leave the primary workspace parked on a merged or superseded topic branch.

### Treat coding-agent context as a constrained resource

The coding agent should optimize its own context/token use before optimizing local-model inference cost. The goal is to make more implementation progress between context resets without sacrificing correctness.

- Start routine work with `python scripts/agent_context.py --focus "<task>" --issue <issue>`; the generator refreshes deterministic implementation discovery before assembling the packet.
- Start with explicit handoff required reads and source-catalog matches. Query `python refs/tools/generate_source_catalog.py --query "<task or symbol>"` before broad source search when the packet is insufficient.
- Prefer symbol-level or targeted file ranges, diffs, tests, and deterministic diagnostics over repeatedly loading whole large files or directories.
- Expand context only for a concrete dependency, ambiguity, failing test, system boundary, or authoritative reference. Do not recursively read or summarize the repository as routine preparation.
- Do not re-read unchanged material already established in the active work session unless new evidence makes it relevant.
- Use deterministic tools for mechanical questions: parsers, formatters, schema validators, targeted tests, database queries, and small diagnostic scripts should replace repeated natural-language reasoning whenever practical.
- If substantially the same diagnostic, transformation, comparison, or validation is performed twice in one development arc, make it reusable before doing it a third time.
- Batch related inspections and edits into coherent slices. Avoid one-tool-call-per-line workflows and speculative ping-pong between files.
- Persist context-heavy findings and next steps in `refs/handoffs/currentHandoff.md` so a reset does not require rediscovering accepted state.
- Prefer concise evidence summaries and references to durable files over pasting large unchanged source blocks into prompts or comments.
- Do not build abstractions for genuinely one-off work solely to save tokens; create tooling where repetition or deterministic reuse is expected.

### Use bounded sub-agents deliberately

When the environment supports sub-agents, delegate independent bounded work by default when doing so reduces parent-agent context, enables useful parallel work, or isolates a specialized task.

- Use the least expensive capable sub-agent/model for the delegated work.
- Good lower-cost/read-only delegation targets include bounded search, call-site discovery, test inspection, log/diagnostic classification, documentation consistency checks, and narrow comparisons.
- Do not delegate when coordination cost exceeds the task, when the work requires the parent's complete context, or when parallel writes create material merge/conflict risk.
- Prefer read-only sub-agent work when multiple agents could touch overlapping files.
- The parent agent owns integration, conflict resolution, tests, validation, and final correctness.

Delegation is a context-management technique, not a requirement to fragment trivial work.

### Keep source modular enough for bounded reasoning

Hand-authored implementation code should favor cohesive, atomic ownership rather than large multi-purpose files.

- Prefer one cohesive responsibility per source module. A file should be explainable in one short sentence without joining unrelated responsibilities with "and".
- Keep functions and modules small enough that an agent or human can inspect the relevant behavior with a targeted symbol or line-range read rather than loading a large multi-purpose file.
- Do not add a new independent responsibility to a file that already mixes unrelated concerns. Split the new responsibility, or decompose the existing file first when doing so can be done safely within the task.
- Separate orchestration, domain logic, persistence, external adapters, presentation, state management, and pure transformations when they can evolve or be tested independently.
- Avoid catch-all modules such as `utils`, `helpers`, `service`, or `manager` when the contents span multiple domains. Prefer semantic module names that expose purpose and ownership.
- Prefer explicit imports and narrow public surfaces so generated source discovery can represent dependencies and callable boundaries usefully.
- Large-file thresholds may be project-specific, but line count alone is not the rule. Generated code, declarative data, migrations, protocol bindings, and other cohesive artifacts may legitimately be large.
- When a file is difficult to summarize, difficult to test without unrelated setup, or repeatedly requires broad reads for small changes, treat that as evidence that the module should be decomposed.

The goal is bounded reasoning, not aesthetic file splitting: a change should normally require loading only the source units that own the behavior being changed.

### Start resets with the generated context packet

For routine continuation, run:

```powershell
python scripts/agent_context.py --focus "<short task description>" --issue <issue-number>
```

The packet is intentionally small and derived from authoritative refs, the generated source catalog, and local git state. It includes branch/SHA, explicit required reads, source-catalog symbol/range matches, current handoff highlights selected for the focus, relevant accepted decisions, file-map hints, changed paths, and required validation commands. It is orientation, not a new source of truth.

Use the packet to drive progressive loading:

1. Read the required reads and source-catalog matches first.
2. Inspect diffs from the accepted integration branch before reopening unchanged source.
3. Query the catalog before broad search if implementation ownership is still unclear.
4. Prefer symbol/range reads before whole-file reads.
5. Expand to the complete roadmap, decision register, architecture docs, or handoff only when a concrete dependency or boundary requires it.
6. Do not re-derive an accepted decision merely because a reset occurred.

The packet prints to stdout by default. `--output .agent-context.md` may be used as a local scratch artifact; that file is ignored by Git and must not be committed. `--check` validates catalog freshness plus packet generation inside the routine size budget.

### Maintain the generated source catalog

`refs/tools/generate_source_catalog.py` is deterministic static-analysis discovery over Git-visible implementation source. It is derived evidence only; source files and tests remain authoritative.

- Python uses AST extraction. Supported non-Python languages use conservative deterministic syntax patterns.
- Records expose path, content hash, imports/file dependencies, callable name, line range, signature, inputs, output, static call dependencies, and dependency targets when they can be resolved safely.
- Dynamic dispatch, reflection, dependency injection, generated code, framework wiring, and runtime ownership may still require targeted source/test inspection.
- The detail catalog is sharded by stable path hash so ordinary source edits update only one shard plus the compact root index.
- Do not hand-edit `refs/implementation/sourceCatalog/index.yaml` or `refs/implementation/.sourceCatalogShards/shard-*.yaml`.
- Regenerate after source changes and require `python refs/tools/generate_source_catalog.py --check` before finalizing.
- If extraction semantics change materially, increment the catalog format version so cached records rebuild deterministically.

### Start long work as a draft pull request

Use a draft pull request when work is expected to require several commits, iterative diagnostics, temporary incompatibility, or cross-stack changes. Keep it draft until the branch represents a coherent checkpoint that is worth validating and reviewing.

A draft is not permission to publish random damage. The branch should still remain understandable and recoverable.

### Validate locally before publishing a checkpoint

Run the cheapest relevant checks before pushing whenever the execution environment supports them. At minimum, validate the files and subsystem changed. Run broader checks before marking the pull request ready.

When local execution is unavailable, batch related changes into a coherent remote checkpoint rather than pushing one speculative fix at a time.

### Do not use notification-generating commits as a debugger

Do not repeatedly push tiny guesses to a branch whose workflows notify on failure. Read the existing failure first, identify the smallest plausible cause, and publish a coherent fix.

When logs are difficult to retrieve:

- Prefer the existing Actions logs and job annotations.
- Prefer local reproduction or a clean checkout.
- Prefer a manually dispatched diagnostic workflow or an artifact-producing diagnostic step.
- Do not add push-triggered one-shot workflows that commit their own output back to the branch.
- Do not commit transient diagnostic logs to the repository.

A temporary diagnostic workflow, when genuinely necessary, must be manual-only, narrowly scoped, and removed in the same pull request before merge.

### Treat generated and compile-time assets as part of the build contract

Frameworks such as Tauri validate configuration, icons, capabilities, schemas, and generated context during compilation. Before enabling a new build target in required CI, verify its complete compile-time input set locally or in one deliberate checkpoint.

A source file compiling is not enough when a framework macro consumes repository configuration and assets.

### Keep expensive gates behind cheap gates

Fast generated-state checks, formatting, lint, unit, and frontend checks should run before expensive native builds, packaging, integration environments, or end-to-end suites. Expensive jobs should use `needs` so obvious failures stop early.

### Cancel obsolete work

Every PR-facing workflow should use a concurrency group based on the workflow and pull request or branch. New commits should cancel older in-progress runs unless the workflow produces durable release artifacts that must finish.

### Preserve meaningful notifications

Do not silence all failure notifications to compensate for noisy workflow design. Fix the workflow so an email represents a meaningful failed checkpoint. Failures on `main`, `dev`, release branches, and ready-for-review pull requests should remain visible.

## Review checklist

Before marking a pull request ready:

- The branch contains a coherent, reviewable increment.
- Temporary workflows, logs, generated diagnostics, and repair scaffolding are removed.
- The expected local or targeted checks have passed.
- Generated source-catalog and OKF index state is current.
- Framework configuration and required assets are present.
- The full CI workflow is expected to pass, not merely hoped to reveal the next clue.
- Public-repository privacy boundaries have been checked.

## Current Nerve Center validation order

1. Tracked-path, generated source-catalog/OKF state, refs, agent-context, Python install/lint/tests.
2. React and TypeScript production build.
3. Tauri Rust `cargo check`, after the first two jobs pass.

The workflow can be manually invoked from GitHub Actions when a draft branch reaches a useful checkpoint but is not yet ready for general review.
