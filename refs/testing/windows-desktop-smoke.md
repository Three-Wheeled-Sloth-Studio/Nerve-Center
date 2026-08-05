# Windows Desktop Smoke Test

## Purpose

Validate the assembled unsigned Windows development package on a real Windows machine. This checklist covers installer, packaged-backend, tray, persistence, failure-reporting, and cleanup behavior that source CI cannot prove.

Record before testing:

- Nerve Center version and commit.
- Windows edition and version.
- Machine architecture.
- Installer artifact name.
- Whether Python, Node.js, and Rust are installed.
- Whether another Nerve Center service is already running.

## Install and first launch

1. Start from a machine or Windows user profile without an existing Nerve Center installation when practical.
2. Run the unsigned NSIS installer.
3. Confirm Windows presents the expected unsigned-development warning rather than an unexpected publisher identity.
4. Complete the per-user installation without administrator elevation.
5. Launch Nerve Center from the installed shortcut.
6. Confirm the startup screen appears while the local service initializes.
7. Confirm the application reaches the normal review interface without requiring a separate Python installation or virtual environment.
8. Confirm the health endpoint reports the packaged application version.
9. Confirm the runtime database and backend log are created under the operating-system application-data and log locations, not in the installation directory or repository checkout.

## Core runtime and tray lifecycle

1. Create and start a bounded synthetic or Job Scout run with safe test configuration.
2. Confirm the run enters an active state and progress remains visible.
3. Close the main window using the window close control.
4. Confirm the window hides rather than terminating the application.
5. Confirm the active run continues while the main window is hidden.
6. Restore Nerve Center from the tray icon.
7. Confirm the same run and persisted state remain visible.
8. Cancel the run and confirm the state transition completes.
9. Repeat close and restore with no active run.

## Explicit quit and restart

1. Choose **Quit** from the tray menu.
2. Confirm the desktop process exits.
3. Confirm the backend process owned by the desktop also exits.
4. Confirm no duplicate or orphaned `nerve-center-api.exe` remains.
5. Relaunch Nerve Center.
6. Confirm the application becomes ready and prior persisted records remain available.
7. Confirm only one managed backend process is running.

## Existing service and port conflict

### Existing healthy Nerve Center service

1. Start a compatible Nerve Center API manually on `127.0.0.1:8765`.
2. Launch the desktop application.
3. Confirm the shell adopts the existing healthy service and reports it as an existing or external service.
4. Quit the desktop application.
5. Confirm the pre-existing service continues running because the desktop did not create or own it.

### Unrelated port occupant

1. Stop Nerve Center services.
2. Start an unrelated local HTTP service on port `8765` that does not return the Nerve Center health payload.
3. Launch Nerve Center.
4. Confirm the startup screen reports a port conflict or unexpected health response.
5. Confirm Nerve Center does not kill the unrelated process.
6. Stop the unrelated process and choose the startup retry action.
7. Confirm Nerve Center starts its packaged backend and reaches ready state.

## Backend failure and recovery

1. Launch Nerve Center and wait for ready state.
2. Terminate the managed `nerve-center-api.exe` process from Task Manager.
3. Confirm the desktop detects the stopped or unhealthy backend and shows a startup/runtime failure surface.
4. Confirm the local diagnostic-log path is displayed.
5. Inspect the log and confirm it contains operational backend output without resume contents, application records, prompts, credentials, cookies, or browser-session data.
6. Choose the retry action.
7. Confirm a new backend process starts and the UI returns to ready state.
8. Confirm no duplicate backend remains after recovery.

## Startup failure reporting

Exercise at least one controlled startup failure, such as temporarily configuring `NERVE_CENTER_API_EXECUTABLE` to a nonexistent path in a development launch.

Confirm:

- The UI does not remain on an indefinite spinner.
- The error message distinguishes launch failure from health timeout or port conflict.
- The diagnostic path is local and actionable.
- Retry is available.
- Clearing the bad configuration permits a successful retry or relaunch.

## Privacy and repository boundary

After the full test:

1. Search the source checkout and installation directory for new database, resume, profile, browser, application, generated-document, and log files.
2. Confirm none were written there.
3. Confirm generated backend build output is not tracked by git.
4. Confirm logs do not contain credentials, authentication cookies, full personal source documents, or generated personalized artifacts.
5. Confirm all durable user state remains under operating-system application data.

## Uninstall

1. Quit Nerve Center explicitly.
2. Uninstall it through Windows Settings or the installed uninstaller.
3. Confirm installed program files and shortcuts are removed.
4. Record whether local application data remains. For this development increment, preserving user data is acceptable and should be explicit; silent deletion is not required.
5. Confirm no Nerve Center process remains after uninstall.

## Result record

Record:

- Overall result: pass, pass with caveats, or fail.
- Each failed checklist item.
- Relevant screenshots or redacted diagnostic excerpts.
- Installer artifact and commit tested.
- Any manual workaround required.
- Whether Issue #10 acceptance criteria are met on the tested machine.

Do not mark real-machine desktop validation complete based only on GitHub-hosted Windows compilation or packaging. This checklist requires an installed artifact exercised interactively on Windows.
