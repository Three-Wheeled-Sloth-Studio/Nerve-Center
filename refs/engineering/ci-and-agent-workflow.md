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

`dev` is Nerve Center's active integration and development branch. Topic branches may be used for
reviewable pull requests, but after a topic branch is merged, switch the active working checkout to
`dev`, update it to the accepted merge commit, and continue work from `dev`. Do not leave the primary
workspace parked on a merged or superseded topic branch.

### Treat coding-agent context as a constrained resource

The coding agent should optimize its own context/token use before optimizing local-model inference cost. The goal is to make more implementation progress between context resets without sacrificing correctness.

- Read `refs/implementation/fileMap.yaml` before broad repository search and start from the smallest likely source set.
- Prefer targeted file ranges, symbol searches, diffs, and tests over repeatedly loading whole large files or directories.
- Do not re-read unchanged material already established in the active work session unless new evidence makes it relevant.
- Use deterministic tools for mechanical questions: grep/search, parsers, formatters, schema validators, targeted tests, database queries, and small diagnostic scripts should replace repeated natural-language reasoning whenever practical.
- If substantially the same diagnostic, transformation, comparison, or validation is performed twice in one development arc, make it reusable before doing it a third time.
- Batch related inspections and edits into coherent slices. Avoid one-tool-call-per-line workflows and speculative ping-pong between files.
- Persist context-heavy findings and next steps in `refs/handoffs/currentHandoff.md` so a reset does not require rediscovering accepted state.
- Prefer concise evidence summaries and references to durable files over pasting large unchanged source blocks into prompts or comments.
- Do not build abstractions for genuinely one-off work solely to save tokens; create tooling where repetition or deterministic reuse is expected.

### Start resets with the generated context packet

For routine continuation, run:

```powershell
python scripts/agent_context.py --focus "<short task description>" --issue <issue-number>
```

The packet is intentionally small and derived from authoritative refs plus local git state. It includes branch/SHA, current handoff highlights selected for the focus, relevant accepted decisions, file-map hints, changed paths, and required validation commands. It is orientation, not a new source of truth.

Use the packet to drive progressive loading:

1. Read the active issue/task and the specific paths the packet identifies.
2. Inspect diffs from the accepted integration branch before reopening unchanged source.
3. Use symbol search or targeted line ranges before reading whole files.
4. Expand to the complete roadmap, decision register, architecture docs, or handoff only when the task crosses those boundaries or the packet lacks necessary context.
5. Do not re-derive an accepted decision merely because a reset occurred.

The packet prints to stdout by default. `--output .agent-context.md` may be used as a local scratch artifact; that file is ignored by Git and must not be committed. `--check` validates that generation still works and remains inside the routine size budget.

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

Fast formatting, lint, unit, and frontend checks should run before expensive native builds, packaging, integration environments, or end-to-end suites. Expensive jobs should use `needs` so obvious failures stop early.

### Cancel obsolete work

Every PR-facing workflow should use a concurrency group based on the workflow and pull request or branch. New commits should cancel older in-progress runs unless the workflow produces durable release artifacts that must finish.

### Preserve meaningful notifications

Do not silence all failure notifications to compensate for noisy workflow design. Fix the workflow so an email represents a meaningful failed checkpoint. Failures on `main`, `dev`, release branches, and ready-for-review pull requests should remain visible.

## Review checklist

Before marking a pull request ready:

- The branch contains a coherent, reviewable increment.
- Temporary workflows, logs, generated diagnostics, and repair scaffolding are removed.
- The expected local or targeted checks have passed.
- Framework configuration and required assets are present.
- The full CI workflow is expected to pass, not merely hoped to reveal the next clue.
- Public-repository privacy boundaries have been checked.

## Current Nerve Center validation order

1. Agent-context generation and Python install/lint/tests.
2. React and TypeScript production build.
3. Tauri Rust `cargo check`, after the first two jobs pass.

The workflow can be manually invoked from GitHub Actions when a draft branch reaches a useful checkpoint but is not yet ready for general review.
