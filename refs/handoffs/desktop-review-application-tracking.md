# Desktop Review and Application Tracking Handoff

## Accepted target

- Integration branch: `dev`.
- Pull request: `#8`.
- Visible version: `0.5.0`.
- SQLite schema version: `6`.
- Tracking issue: `#5`.

## Implemented

### Application tracking

Nerve Center stores one durable pursuit record per opening and append-only status events. Supported states cover discovery, saved and dismissed review states, planned and active application work, recruiter and interview stages, offers, rejection, withdrawal, and closure without response.

The record also supports application date, source, resume variant reference, referral state, response date, disposition reason, and notes. Moving to `applied` records the application date when one was not supplied. Moving into a response state records the response date. Repeating an unchanged status does not create duplicate status history.

### Review service

`GET /api/v1/review/opportunities` joins the normalized opening, company, latest score, current application state, and a suggested next action. It supports priority, response, fit, and freshness sorting and hides dismissed opportunities unless requested.

The Python service remains authoritative. The desktop is a replaceable local client.

### React review client

The desktop client provides:

- Searchable and sortable opportunity review.
- Compact priority, fit, response, value, and confidence summaries.
- Progressive disclosure for score factors, gates, provenance, and the original description.
- Original listing and company-career actions.
- Save, dismiss, plan-to-apply, and full application-status updates.
- A one-step undo for pursuit status changes.
- Duration and fixed-window Job Scout controls.
- Active-run status, active source summaries, cancellation, and run history.
- Pursuit-rule management.
- Positioning-hypothesis approval and disapproval.
- Location and scoring-weight preferences.

The UI explicitly states that it never submits applications, contacts employers, or changes the career profile automatically.

### Tauri v2 shell

The shell starts the local Python service when enabled, shows and restores the main window from the system tray, hides the window rather than terminating when the close control is used, and stops its managed API child only when the user chooses Quit.

Environment overrides:

- `NERVE_CENTER_PYTHON`: explicit Python executable.
- `NERVE_CENTER_API_MANAGED=0`: do not start or stop the API process.

The shell includes explicit PNG and ICO application assets for compile-time context generation and later Windows packaging work.

### Validation

CI validates three independent surfaces:

1. Python Ruff and Pytest.
2. TypeScript compilation and the Vite production build.
3. Tauri Rust `cargo check` with Linux desktop dependencies.

Application tests cover automatic dates, append-only and idempotent status history, dismissed filtering, restoration, and review aggregation.

## Known limits

- A signed Windows installer is not produced yet.
- The managed API process assumes an installed Python environment containing the Nerve Center package.
- A real Windows tray and window lifecycle smoke test must still be run on a Windows machine.
- The desktop currently polls run state rather than using push events.
- Score and enrichment generation remain explicit service operations; the review client does not silently invoke an LLM.
- No applications, outreach, profile changes, authenticated job-board actions, cloud sync, or multi-user behavior are implemented.

## Next increment

The next useful work is packaging and operational hardening: a repeatable Windows build, Python runtime resolution, installer and upgrade behavior, startup health reporting, and a real-machine desktop smoke-test checklist. Keep the local-only and consequential-action boundaries intact.
