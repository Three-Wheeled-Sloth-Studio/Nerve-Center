# Job Scout input quality QA

## Scope

Issue #14 covers the first interactive QA pass on the Job Scout setup workspace.

## Reported defects

- Resume setup required a typed local path and provided no browse/select affordance.
- Target Titles and Locations parsed on every keystroke, which stripped trailing spaces before users could finish phrases.
- Commas were treated as separators, so locations such as `Raleigh, NC` could not be retained.
- Multi-value fields did not consistently define Windows CRLF behavior.
- Relevant Terms promoted generic resume prose and document locator words instead of meaningful search concepts.
- Generated keywords were persisted in the same field as manual additions, destroying provenance and carrying noise forward.

## Implemented behavior

- The resume card provides an accessible folder-icon button backed by the native operating-system file chooser.
- Selected PDF, DOCX, Markdown, or text files are transferred to module-owned durable storage and imported through the normal document pipeline.
- The original selected file name remains visible after import; users are not asked to discover or type an absolute path.
- Multi-value fields keep raw draft text while editing and materialize arrays only for Save, Rediscover, or Scan actions.
- CRLF, LF, and lone CR line endings are accepted. Commas are never delimiters.
- Target titles and locations preserve spaces and punctuation exactly after trimming surrounding whitespace.
- Manual keyword additions now use `manual_keywords`; the legacy mixed-provenance `keywords` field is accepted only for migration and is discarded on the next configuration write.
- Deterministic keyword discovery prioritizes configured titles, profile labels/headlines, manual phrases, repeated evidence terms, technical identifiers, and meaningful two- or three-word phrases.
- Generic terms such as `paragraph` and `across` are filtered, and raw segment locators are no longer analyzed as resume content.

## Versioning

- Application version: `0.12.1`
- Job Scout module data schema: `3`
- Core SQLite schema: unchanged

## Regression coverage

- Desktop build executes `desktop/scripts/test-multivalue.mjs` against the actual TypeScript parser and verifies CRLF, LF, lone CR, spaces, commas, trimming, and deduplication.
- Python integration tests exercise the browser-upload endpoint, durable storage, original file-name retention, configuration round-tripping, meaningful keyword extraction, generic-term rejection, and legacy keyword cleanup.

## Manual QA path

1. Open Job Scout and choose the folder icon beside Resume file.
2. Select a supported resume without typing a path and load it.
3. Enter `Principal Product Manager` and `Director of Product` on separate lines.
4. Enter `Raleigh, NC` and `Washington, DC` on separate lines.
5. Save, leave the module, return, and confirm all phrases and punctuation round-trip unchanged.
6. Paste the same values using Windows CRLF line endings and repeat the save.
7. Rediscover terms and confirm generic document words such as `paragraph` and `across` are absent.
8. Add a manual phrase, rediscover, and confirm it remains present without generated terms appearing in Manual additions.
