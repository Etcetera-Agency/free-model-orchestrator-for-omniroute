# Change: Live quota ingestion

## Why

Quota reset and reclassification currently run on caller-provided quota numbers.
They need concrete provider/OmniRoute quota fetchers wired in, with auth,
retries, stale-data handling, and tests for unavailable quota sources.

## What Changes

- Wire live quota fetchers into quota reset/reclassification with auth and
  bounded retries: OmniRoute `GET /api/usage/quota` (and related
  `GET /api/usage/provider-limits` / `GET /api/usage/token-limits`) or the
  provider's own quota surface.
- Handle stale or unavailable quota sources by failing closed (no usable capacity
  inferred) rather than assuming fresh data.
- Record realistic quota-source fixtures for deterministic tests of this
  boundary.

## Impact

- Affected specs: `quota-manager`
- Affected code (later): `src/fmo/quota_manager.py`, `src/fmo/omniroute.py`
- Spec-only proposal; no implementation in this change.
