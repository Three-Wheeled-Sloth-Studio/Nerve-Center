# Core and Module Boundary Handoff

## Accepted baseline

- Branch: `dev`
- Version: `0.7.0`
- Product authority: `refs/planning/product-requirements-document.md`
- Package contract: `refs/planning/module-package-contract.md`

## Implemented

- Versioned module manifest and module API contracts.
- Compatibility bounds, data-schema version, launch metadata, task types,
  permissions, storage namespace, configuration schema, and UI contributions.
- Registry validation for package compatibility and exact declared task
  implementations.
- Durable `core_modules` inventory with Enabled, Paused, and Not Installed
  lifecycle states.
- Manager-created module data roots outside the checkout.
- Module inventory and lifecycle API routes.
- Run-admission rejection for paused modules.
- Job Scout manifest and composition adapter.
- Desktop module inventory, lifecycle control, and manifest-derived Job Scout
  task selection.
- Explicit ownership map for existing core and Job Scout tables.

## Migration constraints

- Job Scout still executes through an in-process adapter. This is explicit in
  its launch manifest and is the starting point for Increment 8.
- Existing Job Scout table names were preserved to avoid a risky no-value data
  migration during boundary extraction.
- The synthetic task remains manager-owned diagnostic work and is intentionally
  outside the installed-module inventory.
- UI renderer keys resolve to trusted compiled components; arbitrary package
  JavaScript is not supported.

## Validation

Run:

```powershell
.venv\Scripts\ruff.exe check src tests
.venv\Scripts\python.exe -m pytest
cd desktop
npm run build
cd src-tauri
cargo check
```

Focused module tests:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_module_contracts.py tests/test_module_registry.py tests/test_api.py
```

## Next increment

Implement Increment 8 from `refs/planning/mvp-roadmap.md`:

1. Replace `in_process_adapter` execution with supervised child processes.
2. Define the scoped runtime-token and loopback protocol.
3. Pass manager-owned run context and assigned storage at launch.
4. Add heartbeat, health, activity, backlog, and queue-pressure reporting.
5. Apply Enabled and Paused state to process launch and graceful shutdown.
6. Preserve the accepted package startup-health baseline.
