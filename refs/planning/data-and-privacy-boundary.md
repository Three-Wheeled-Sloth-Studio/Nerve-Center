# Data and Privacy Boundary

## Public source repository

The repository may contain application source, synthetic fixtures, generic schemas, migrations, public documentation, and redacted examples. It must not contain real candidate data, personal documents, application histories, browser sessions, credentials, or private recruiter communication.

## Local durable data

The following data belongs in the operating system application-data directory:

- Canonical career evidence and user corrections.
- Resume and cover-letter source references.
- Search plans and learned positioning decisions.
- Companies, domains, source health, and posting history.
- Job descriptions, provenance, scores, and explanations.
- Application status and outcome history.
- Generated personalized artifacts.
- Bounded and redacted runtime logs.
- Dedicated browser automation profiles.

Original documents should remain read-only. Generated variants are new artifacts with provenance back to the master and transformation contract.

## Credentials

API keys and other secrets must not be stored in SQLite as plain text. Prefer the Windows Credential Manager through a narrow credential-service abstraction. Environment variables may be used for development but populated files remain outside version control.

## Search-provider disclosure

Search providers receive generated search queries, never the full resume or canonical evidence profile. Remote LLM providers, when eventually enabled, require an explicit data-boundary review and opt-in.

## Logging

Logs must avoid full page bodies, resumes, cover letters, credentials, cookies, and complete user search histories. Store identifiers, connector state, timing, status, error class, and redacted diagnostic context. Logs must have configurable retention and size bounds.

## Browser isolation

Browser automation uses a dedicated profile created for Nerve Center. It may preserve ordinary unauthenticated cookies needed for continuity and challenge handoff, but it must never load the user's daily browser profile or authenticated LinkedIn state.
