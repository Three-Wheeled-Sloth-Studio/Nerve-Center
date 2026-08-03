# Security Policy

Nerve Center is a public source repository for a local application that may process highly sensitive personal and job-search information.

## Never commit

Do not commit any of the following, even temporarily:

- Resumes, cover letters, career histories, or identity documents.
- Job application records or private recruiter communications.
- Browser profiles, cookies, session tokens, or authenticated page captures.
- API keys, passwords, private keys, credentials, or populated environment files.
- Local databases, logs, exports, or generated documents containing personal information.
- Screenshots or test fixtures derived from real user data unless they have been deliberately and irreversibly anonymized.

The `.gitignore` is a backstop, not a security boundary.

## Runtime storage

Durable user data must be stored outside the repository checkout in the operating system's application-data location. Credentials must use the operating system credential store when practical. Logs must be structured, redacted, bounded, and kept outside the checkout.

## Browser automation

Browser automation must use a dedicated unauthenticated profile. It must not reuse a user's normal browser profile or authenticated LinkedIn or job-board session. CAPTCHA or access challenges must not trigger stealth escalation or credential harvesting. Connectors should checkpoint, back off, and support manual continuation.

## Reporting a vulnerability

Open a GitHub security advisory when available. Do not include real credentials, personal documents, or sensitive runtime data in a public issue.
