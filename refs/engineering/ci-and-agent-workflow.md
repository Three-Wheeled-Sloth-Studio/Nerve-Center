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

1. Python install, Ruff, and Pytest.
2. React and TypeScript production build.
3. Tauri Rust `cargo check`, after the first two jobs pass.

The workflow can be manually invoked from GitHub Actions when a draft branch reaches a useful checkpoint but is not yet ready for general review.
