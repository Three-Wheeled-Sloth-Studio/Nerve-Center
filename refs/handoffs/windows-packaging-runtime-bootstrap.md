---
type: Implementation Handoff
title: Windows Packaging and Runtime Bootstrap Handoff
description: Accepted self-contained backend, NSIS packaging, startup supervision, React startup gate, and Windows validation checkpoint.
status: stable
tags: [nerve-center, handoff, windows, packaging]
---
# Windows Packaging and Runtime Bootstrap Handoff

## Accepted target

- Integration branch: `dev`.
- Tracking issue: `#10`.
- Pull request: `#11`.
- Visible version: `0.6.0`.
- SQLite schema version: `6`.
- Initial artifact: unsigned per-user NSIS development installer.

## Implemented

### Self-contained Python backend

The Windows package builds the FastAPI service with PyInstaller as `nerve-center-api.exe`. The generated executable is treated as build output, ignored by git, smoke-tested directly, and then included in the Tauri package as a resource.

The packaged desktop does not require the user to install Python, create a virtual environment, or install the Nerve Center repository package.

Source development preserves the existing Python fallback. Backend selection order is:

1. `NERVE_CENTER_API_EXECUTABLE`, when explicitly configured.
2. The packaged `nerve-center-api.exe` resource.
3. `NERVE_CENTER_PYTHON`, or `python`, as the development fallback.

`NERVE_CENTER_API_MANAGED=0` continues to support an externally started service.

### Packaging-only Tauri configuration

`desktop/src-tauri/tauri.package.conf.json` activates NSIS packaging and maps the generated backend executable into the installed resource directory.

The packaging configuration is passed explicitly:

```powershell
npm run tauri build -- --config src-tauri/tauri.package.conf.json --bundles nsis
```

It is deliberately not named as an automatically merged Windows platform configuration. Normal source compilation therefore does not require the generated PyInstaller executable to exist, avoiding a compile-time Tauri context failure during ordinary development.

### Desktop startup and process supervision

The Tauri shell now owns a startup-health state with visible phases and diagnostics.

Behavior:

- Probe `127.0.0.1:8765/health` before starting a child.
- Adopt an existing healthy Nerve Center service without claiming ownership.
- Reject an unrelated process occupying the port and leave it untouched.
- Start the configured, packaged, or Python fallback backend when management is enabled.
- Wait for database initialization and scheduler startup to complete before reporting ready.
- Detect an early process exit or startup-health timeout.
- Monitor the ready service and report an unexpected process exit or repeated health failure.
- Write backend stdout and stderr to the operating-system application log directory.
- Expose a retry command and local diagnostic-log path to the React client.
- Kill and wait for only the child process owned by the desktop on explicit Quit or managed retry.
- Preserve close-to-tray behavior so closing the main window does not stop active work.

### React startup gate

The normal application UI is hidden until the backend reaches ready state. The startup surface distinguishes initialization from failure and can show:

- Human-readable status.
- Technical failure detail.
- Backend source.
- Managed process ID.
- Local diagnostic-log path.
- A retry action.

Browser-only Vite development uses the same gate by polling the local health endpoint directly.

### Build and validation workflows

The normal CI workflow remains draft-aware and cheap-first. It now also validates the Windows backend packaging command and compiles Rust tests.

The `Windows package` workflow is independently draft-aware and path-filtered. On a Windows runner it:

1. Installs Nerve Center with the packaging extra.
2. Builds the PyInstaller backend.
3. Launches and smoke-tests that executable against `/health`.
4. Installs the desktop dependencies.
5. Builds the unsigned NSIS package with the explicit packaging config.
6. Verifies that an installer was produced.
7. Uploads the installer and unpackaged desktop executable as a 14-day workflow artifact.

Superseded package runs are canceled for the same pull request or branch. The workflow does not publish a release or alter user machines.

## Build commands

From the repository root on Windows:

```powershell
python -m pip install -e ".[packaging]"
python scripts/build_windows_backend.py
python scripts/smoke_packaged_backend.py
```

Then:

```powershell
cd desktop
npm install
npm run tauri build -- --config src-tauri/tauri.package.conf.json --bundles nsis
```

Source development remains:

```powershell
python -m pip install -e ".[dev]"
cd desktop
npm install
npm run tauri dev
```

`launch.bat` also initializes an x64 Visual C++ developer environment before invoking Tauri. It validates candidates by requiring both `excpt.h` and `msvcrt.lib`, so an incomplete newer Visual Studio installation cannot mask a complete fallback Build Tools installation. A shell that already exposes a complete toolchain is preserved. The Windows package workflow runs `scripts/test_visual_cpp_environment.ps1` to cover complete fallback selection, existing-environment preservation, and actionable failure when all candidates are incomplete.

## Validation boundary

Automated validation can prove:

- Python source quality and unit tests.
- Packaging-command construction.
- React and TypeScript production compilation.
- Tauri Rust compilation and health-response tests.
- PyInstaller executable launch and health response on a hosted Windows runner.
- Successful NSIS artifact assembly.

It cannot prove the complete interactive Windows lifecycle. `refs/testing/windows-desktop-smoke.md` remains required for real-machine installer, tray, explicit Quit, persistence, port-conflict, backend-kill, retry, diagnostics, and uninstall validation.

Do not claim the real-machine smoke test is complete until that checklist has been run against an installed artifact.

## Security and privacy boundary

- The generated backend executable is not committed.
- Runtime databases, user documents, application records, browser state, credentials, and logs remain outside the source checkout.
- Diagnostic UI exposes a local path and operational errors, not personal document contents.
- The packaged product preserves the permanent prohibition on automatic applications, outreach, profile changes, and authenticated job-board automation.

## Deferred

- Code signing and trusted publisher identity.
- Automatic updates and release channels.
- Public download or release publication.
- Upgrade and rollback policy beyond ordinary NSIS replacement behavior.
- Cross-platform packaging.
- Wake-from-sleep.
- Product-feature expansion unrelated to packaging.

The next operational increment should begin only after the real-machine smoke checklist identifies any installer or lifecycle defects. Signing, updater, and release-channel work should remain a separate PI.
