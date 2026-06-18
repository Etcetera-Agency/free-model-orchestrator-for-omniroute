# Change: Real OmniRoute catalog ingestion

## Why

The provider scanner currently accepts prebuilt catalog payloads only. Daily
catalog scans need to fetch real provider/model catalogs from OmniRoute with
authentication, retries and structured errors so snapshots reflect live state.

## What Changes

- Add a live OmniRoute catalog fetch via the OmniRoute client: provider accounts
  from `GET /api/providers` and the model catalog from
  `GET /api/v1/providers/{provider}/models` (per provider) / `GET /v1/models`,
  with auth/config, bounded retries, and structured fetch errors that mark the
  snapshot failed instead of fabricating a catalog.
- Record realistic OmniRoute catalog fixtures and add snapshot integration tests.

## Impact

- Affected specs: `provider-scanner`
- Affected code (later): `src/fmo/scanner.py`, `src/fmo/omniroute.py`
- Spec-only proposal; no implementation in this change.
