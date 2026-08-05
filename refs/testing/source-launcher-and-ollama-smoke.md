# Source Launcher and Ollama Smoke Test

## Purpose

Verify that a Windows source checkout can bootstrap its local dependencies, start
the Tauri desktop shell and manager-owned API, and discover installed Ollama models
through the provider-neutral catalog.

This is separate from `windows-desktop-smoke.md`, which validates the assembled
installer and packaged backend.

## Preconditions

- Windows x64.
- Node.js 22 or newer.
- Stable Rust toolchain and Tauri v2 Windows prerequisites.
- Python 3.12 or newer when `.venv` must be created.
- Ollama installed and running for model discovery.

## Launch

From the repository root:

```powershell
.\launch.bat
```

Keep the desktop application running during API checks. The shell owns the API
lifecycle, so choosing **Quit** also stops the service on port `8765`.

The launcher must:

1. Validate Node.js and Rust prerequisites.
2. Create `.venv` with Python 3.12 or newer when it is absent.
3. Restore `pip` with `ensurepip` when an existing environment lacks it.
4. Compare the installed `nerve-center` version with `pyproject.toml` and refresh
   the editable install when missing or stale.
5. Install desktop dependencies when `desktop/node_modules` is absent.
6. Warn, without blocking launch, when Ollama is absent or not responding.
7. Set `NERVE_CENTER_PYTHON` to the repository virtual-environment interpreter.
8. Start the Tauri shell, Vite client, and managed API without orphaning a second
   API process.

## API checks

In a second PowerShell window:

```powershell
Invoke-RestMethod http://127.0.0.1:8765/health |
  ConvertTo-Json -Depth 4

Invoke-RestMethod http://127.0.0.1:8765/api/v1/providers/models |
  ConvertTo-Json -Depth 6
```

Expected results:

- Health returns `status: ok` and the version from `pyproject.toml`.
- The provider endpoint returns one catalog entry per installed Ollama model.
- Every entry identifies the provider as `ollama` and includes model identity,
  metadata, declared capabilities, hardware-fit observations, and `last_seen_at`.
- Unsupported hardware observations remain `unmeasured`; they are not inferred from
  model names.

## Verified result: 2026-08-05

- Branch: `dev`
- Baseline commit: `d8f1314`
- Application version: `0.11.0`
- Result: pass
- Health: HTTP 200, `status: ok`, version `0.11.0`
- Catalog count: 5
- Models: `codellama:latest`, `gemma4:latest`, `gpt-oss:latest`,
  `qwen2.5-coder:latest`, `qwen2.5:7b-instruct`
- Observed host fields: Windows, AMD64, 16 logical CPUs
- Unmeasured fields: memory fit and accelerator fit

## Troubleshooting

`Unable to connect to the remote server` means no Nerve Center API is listening.
Confirm the desktop shell remains open and check:

```powershell
Get-NetTCPConnection -LocalPort 8765 -State Listen
Get-Content "$env:LOCALAPPDATA\org.threewheeledsloth.nervecenter\logs\backend.log" -Tail 100
```

If the launcher reports an unrelated occupant on port `8765`, stop that application
or move it before retrying. Nerve Center must not terminate unrelated processes.
