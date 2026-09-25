# Security Policy

## Supported versions

Rocqet is deployed as a single rolling `main` branch (see [DEPLOY.md](DEPLOY.md)) —
there are no maintained older versions. Security fixes land on `main`.

## Reporting a vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities.

Instead, use GitHub's private vulnerability reporting:

1. Go to the [Security tab](../../security) of this repository.
2. Click **"Report a vulnerability"**.

This opens a private advisory visible only to maintainers until a fix is ready.
If that option isn't available, contact the maintainer directly via
[@still-rollin](https://github.com/still-rollin) on GitHub.

Please include:

- A description of the vulnerability and its potential impact.
- Steps to reproduce (a minimal request/query is ideal).
- Any relevant logs or stack traces.

We'll acknowledge reports within a few days and keep you updated as we work on
a fix.

## Scope notes

- The public API (`/search`, `/stats`, `/health`) is read-only and rate-limited;
  it accepts no user-supplied code or credentials.
- Serving is LLM-free by design (see [CONTRIBUTING.md](CONTRIBUTING.md)) — the
  hosted API never executes model calls at request time, which limits the
  prompt-injection/LLM-abuse surface.
- Reports about retrieval *quality* (irrelevant results, missing declarations)
  are welcome but aren't security issues — please file those as a regular
  [GitHub issue](../../issues) instead.
