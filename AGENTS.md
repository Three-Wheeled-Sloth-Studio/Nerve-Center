# Nerve Center Agent Entry Point

Before changing Nerve Center, read these in order:

1. `refs/project.yaml`
2. `refs/agents.yaml`
3. `refs/planning/mvp-roadmap.md`
4. `refs/planning/decision-register.md`
5. `refs/planning/product-vision-and-architecture.md` when changing boundaries or runtime shape
6. `refs/implementation/fileMap.yaml` before broad repository searches
7. `refs/testing/validationCommands.yaml` before finalizing work
8. `refs/handoffs/currentHandoff.md` for the latest context-heavy checkpoint

`refs/index.md` is the generated OKF discovery surface. It is useful for navigation, but it does not replace the required reading order above.

Do not hand-edit generated `refs/**/index.md` files. Regenerate them with `python refs/tools/generate_okf_indexes.py`.

Do not store secrets or machine-local credentials in `refs/`.
