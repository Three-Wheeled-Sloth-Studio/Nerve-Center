# Career Evidence Profile Handoff

## Accepted baseline

- Branch: `dev`.
- Accepted code through commit: `5cbfc2036574fb59afd4e4e1712cf97f3c7355e6` plus this documentation commit.
- Visible version: `0.2.0`.
- Schema version: `3`.
- Python requirement: `3.12+`.
- Tracking issue: `#2`.

## Implemented

### Provider-neutral structured generation

The provider contract supports model discovery and schema-constrained generation without exposing Ollama-specific behavior to profile logic.

The Ollama adapter:

- Lists local models through the native tags endpoint.
- Uses the native chat endpoint with `stream` disabled.
- Passes the Pydantic JSON schema through Ollama's structured-output `format` field.
- Uses temperature zero for repeatable extraction behavior.
- Validates returned JSON through the requested Pydantic response model.
- Retries transient local network, timeout, 429, and server failures once by default.
- Normalizes provider failures into stable, secret-safe error contracts.

Provider telemetry records only operational metadata:

- Provider and model.
- Prompt-contract version and response-schema name.
- Start time and duration.
- Success or safe error code.
- Retry count.
- Input and output character counts.
- Ollama prompt-evaluation and evaluation counts when supplied.

Prompt bodies, resume text, structured output bodies, and credentials are not persisted in provider telemetry.

### Read-only resume source registration

Supported source formats:

- Plain text.
- Markdown.
- DOCX.
- PDF with extractable text.

Registration stores a local absolute source reference, file hash, metadata, and extracted text segments in the application database. The original file is never copied into the repository or application data directory.

The importer:

- Rejects unsupported formats.
- Rejects files larger than 25 MB.
- Rejects encrypted PDFs.
- Reports files with no extractable text.
- Uses stable locators such as line, paragraph, and PDF page-line references.

OCR is intentionally not included. Scanned image-only PDFs will not produce usable text in this increment.

### Canonical career evidence profile

The application maintains one canonical profile rather than user-managed target profiles.

Supported claim categories include:

- Roles.
- Capabilities.
- Industries.
- Methods.
- Technologies.
- Leadership scope.
- Outcomes.
- Constraints.
- Education facts.

Every generated claim must include exact evidence that can be found within its cited source segment. Unsupported evidence is rejected deterministically before it reaches the canonical profile.

The profile records:

- Claim confidence.
- Source-document provenance or explicit user confirmation.
- Proposed, confirmed, and rejected claim decisions.
- Low-confidence review items.
- Invalid-evidence review items.
- Possible contradictions between claims with the same normalized label.

User corrections replace generated evidence with an explicit user-confirmed origin and confidence of one. Confirmed claims survive later extraction passes unchanged. Rejected claims cannot support positioning hypotheses.

### Positioning hypotheses

The model may suggest alternate positioning for the same canonical evidence. Users do not maintain multiple career profiles.

Each hypothesis includes:

- Label and summary.
- Suggested top-level resume headline.
- Supporting canonical claim identifiers.
- Confidence.
- Pending, approved, or disapproved decision.

Decision memory survives later extraction passes. A deterministic similarity check also preserves decisions when the model makes a minor wording change to the same underlying idea. This prevents rejected positioning from returning with a fake mustache.

### Local API

- List Ollama models.
- Register and list local resume sources.
- Extract and merge one source into the canonical profile.
- Inspect the canonical profile.
- Confirm or reject a claim.
- Correct a claim with authoritative user wording.
- Approve or disapprove a positioning hypothesis.

All routes are local-only through the existing FastAPI service.

## Validation

The new Issue #2 test slice passes 11 tests covering:

- Ollama model discovery.
- Schema-constrained chat requests.
- Secret-safe call telemetry.
- Retry telemetry on persistent provider failure.
- Plain-text and Markdown registration.
- DOCX extraction.
- PDF text extraction.
- Exact evidence enforcement.
- Persistent profile storage outside the repository.
- Claim confirmation, rejection, and correction.
- Positioning approval, disapproval, and rephrasing memory.
- Profile API workflows using an injected fake provider.

These tests are isolated from the user's real resume and use synthetic public-safe data.

## Known limits

- A live Ollama model smoke test has not been run from the connector execution environment.
- PDF extraction does not use OCR.
- The current contradiction detector is intentionally conservative.
- Source documents are registered by local path; the desktop file picker belongs to the Tauri increment.
- There is no generated resume or cover-letter output in this increment.
- There is no remote LLM provider.
- Review items do not yet have a dedicated desktop resolution workflow.

## Next increment

Proceed with Issue `#3`, Job discovery source registry and initial connectors.

Required sequence:

1. Define normalized company, source, scan, and job-opening contracts.
2. Persist source classification, health, cadence, and provenance.
3. Implement Greenhouse and Lever public connectors.
4. Add generic `JobPosting` JSON-LD extraction.
5. Add canonical URL normalization and cross-source deduplication.
6. Add direct career-page and sitemap discovery.
7. Add broad unauthenticated search behind a connector boundary.

Do not add opportunity scoring inside the acquisition increment.
