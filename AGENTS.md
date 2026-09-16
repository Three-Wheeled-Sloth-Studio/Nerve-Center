# Nerve Center Agent Entry Point

For routine continuation or a coding-agent reset, start with the compact generated context packet instead of rereading large project documents or the source tree wholesale:

```powershell
python scripts/agent_context.py --focus "<short task description>" --issue <issue-number>
```

The packet is derived orientation only. On ordinary runs it refreshes Nerve Center's deterministic source catalog first, then selects relevant accepted decisions, explicit handoff required reads, source-catalog matches, file-map hints, changed paths, and required validation from authoritative repository state. Do not edit or treat the packet or catalog as runtime truth.

After reading the packet:

1. Start with `Required reads for next slice` and the source-catalog symbol/range matches.
2. If those are insufficient, query `python refs/tools/generate_source_catalog.py --query "<task or symbol>"` before broad repository search.
3. Prefer symbol-level or targeted line-range reads; do not open a whole source file when the relevant symbol, test, or range is sufficient.
4. Expand context only for a concrete dependency, ambiguity, failing test, system boundary, or authoritative reference. Do not recursively read or summarize the repository as routine preparation.
5. Treat accepted decisions as inputs unless new runtime/test evidence contradicts them; do not spend context re-deriving settled choices.
6. Use `refs/testing/validationCommands.yaml` before finalizing work.

For fresh architecture work, unfamiliar subsystems, or changes to module/runtime ownership, use the authoritative reading order below as needed:

1. `refs/project.yaml`
2. `refs/agents.yaml`
3. `refs/planning/mvp-roadmap.md`
4. `refs/planning/decision-register.md`
5. `refs/planning/product-vision-and-architecture.md`
6. `refs/planning/module-package-contract.md`
7. `refs/implementation/fileMap.yaml`
8. `refs/handoffs/currentHandoff.md`
9. `refs/testing/validationCommands.yaml`

`refs/index.md` is the generated OKF discovery surface. `refs/implementation/sourceCatalog/index.yaml` is the compact generated implementation-discovery surface. Neither replaces authoritative refs, source, tests, or runtime evidence.

Conserve coding-agent context and tokens deliberately. Prefer diff-first continuation, source-catalog queries, deterministic diagnostics, tests, and narrow reads over repeated whole-file or whole-repository reads. If substantially the same diagnostic/search/transformation is performed twice in one development arc, make it reusable before doing it a third time.

When the environment supports sub-agents, delegate independent bounded work by default when delegation reduces parent-agent context, enables useful parallelism, or isolates a specialized task. Use the least expensive capable sub-agent/model for bounded search, call-site discovery, test inspection, diagnostics, and documentation checks. Do not delegate when coordination cost exceeds the work, the task requires the parent's full context, or parallel writes create meaningful conflict risk. The parent agent remains responsible for integration and validation.

Keep hand-authored source modular enough for bounded reasoning: prefer one cohesive responsibility per module, separate independently evolving concerns, and treat repeated broad reads for small changes as evidence that a file should be decomposed. See `refs/engineering/ci-and-agent-workflow.md` for the full operating rules.

Do not hand-edit generated `refs/**/index.md` files or source-catalog files. Regenerate OKF indexes with `python refs/tools/generate_okf_indexes.py` and the implementation catalog with `python refs/tools/generate_source_catalog.py`.

Do not store secrets or machine-local credentials in `refs/`.
