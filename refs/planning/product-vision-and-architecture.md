# Nerve Center Product Vision and Architecture

## Vision

Nerve Center is a single-user, local-first desktop orchestration platform. It schedules bounded task runs, coordinates local tools and local language models, persists inspectable state, and presents recommendations without silently performing consequential external actions.

Job Scout is the first task module. It discovers public job openings, interprets a canonical career evidence profile, evaluates opportunities, and prioritizes the positions most likely to produce a useful employer response.

## Architectural shape

```text
Tauri desktop shell
        |
Local HTTP API
        |
Orchestration core
  | scheduler and run windows
  | task registry and plugin contracts
  | resource and concurrency budgets
  | audit and event logging
  | provider-neutral LLM gateway
  | source-compliance registry
        |
Task plugins
  | Job Scout
  | future local-LLM or ComfyUI workflows
        |
SQLite and operating-system application data
```

The desktop shell is not the business-logic host. Scheduling, persistence, connectors, scoring, and task execution live behind reusable service contracts.

## Core platform responsibilities

- Persist duration-based and fixed-time schedules.
- Resolve each requested run to a concrete start and deadline.
- Stop starting new work when a deadline is reached.
- Checkpoint connector and task state for graceful cancellation or resumption.
- Enforce request, domain, browser, LLM, and elapsed-time budgets.
- Route structured prompts through provider-neutral LLM adapters.
- Record model, prompt-contract, scoring-contract, and connector versions.
- Store durable data outside the checkout.
- Expose current state and next action clearly to the desktop UI.

## Job Scout pipeline

```text
resume and confirmed career evidence
        |
canonical evidence profile
        |
search concepts and learned positioning hypotheses
        |
web, ATS, and direct-company discovery
        |
normalization, provenance, and deduplication
        |
location and company enrichment
        |
fit, response, value, and confidence scoring
        |
priority ranking and user review
        |
application outcome tracking and calibration
```

## Consequential-action boundary

The system may recommend and draft. It does not submit, send, post, or alter accounts. Authenticated LinkedIn and job-board sessions are outside automated acquisition. Future resume and cover-letter generation creates reviewable copies from immutable master documents.

## Design principles applied

- Structured state is authoritative.
- LLM output uses schemas and deterministic validation.
- Reversible actions favor undo over modal confirmation.
- Runtime, build output, and user data remain separate.
- Explanations stay close to the decisions they justify.
- Project-specific decisions live here; reusable principles remain in TWS Design Principles.
