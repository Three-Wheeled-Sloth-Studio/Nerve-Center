# Nerve Center Agent Entry Point

For routine continuation or a coding-agent reset, start with the compact generated context packet instead of rereading large project documents wholesale:

```powershell
python scripts/agent_context.py --focus "<short task description>" --issue <issue-number>
```

The packet is derived orientation only. It selects relevant accepted decisions, handoff highlights, file-map hints, changed paths, and required validation from authoritative repository state. Do not edit or treat the packet as a source of truth.

After reading the packet:

1. Read the active issue/task and only the source/ref paths the packet identifies as relevant.
2. Use targeted search and line-range reads before whole-file reads.
3. Expand to `refs/planning/mvp-roadmap.md`, `refs/planning/decision-register.md`, `refs/planning/product-vision-and-architecture.md`, or the full handoff only when the task crosses those boundaries or the compact packet is insufficient.
4. Treat accepted decisions as inputs unless new runtime/test evidence contradicts them; do not spend context re-deriving settled choices.
5. Use `refs/testing/validationCommands.yaml` before finalizing work.

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

`refs/index.md` is the generated OKF discovery surface. It is useful for navigation, but it does not replace authoritative refs.

Conserve coding-agent context and tokens deliberately. Avoid rereading unchanged large files, prefer diff-first continuation and deterministic searches/tests over repeated reasoning, and turn repeated diagnostics or workflows into reusable scripts/tools. If substantially the same diagnostic/search/transformation is performed twice in one development arc, make it reusable before doing it a third time. See `refs/engineering/ci-and-agent-workflow.md` for the full operating rules.

Do not hand-edit generated `refs/**/index.md` files. Regenerate them with `python refs/tools/generate_okf_indexes.py`.

Do not store secrets or machine-local credentials in `refs/`.
