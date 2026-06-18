# Change: Real web-cookie/session acquisition

## Why

Web-cookie providers are deliberately kept out of automatic model discovery but
are **inside orchestration**: per
`reference/docs/architecture/06-omniroute-free-provider-findings.md`, they get
text probe, role scoring (with uncertainty penalty), and quota allocation
**when a usable session/quota exists**. The whole point is to *obtain* those
providers as (lower-weight) free capacity — which requires actually acquiring a
usable session and confirming its health. Today the deterministic candidate
handling exists, but there is no real session acquisition, so these providers
never become usable capacity.

## What Changes

- Acquire web-cookie/session credentials from eligible browser or explicitly
  configured session sources (still never auto-discovered).
- Run live health probes (text probe + session health) and separate the failure
  modes: `expired`, `challenge`, `login_required`, `unsupported_auth`.
- A confirmed-usable session makes the provider eligible for fallback quota
  allocation at reduced weight; any non-confirmed result keeps it unused.
- Record realistic session/probe fixtures for deterministic tests.

## Impact

- Affected specs: `web-cookie-candidates`
- Affected code (later): `src/fmo/web_cookie.py`, `src/fmo/probes.py`
- Spec-only proposal; no implementation in this change.
