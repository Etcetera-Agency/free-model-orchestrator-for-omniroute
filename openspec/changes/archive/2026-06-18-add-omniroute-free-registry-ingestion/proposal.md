# Change: Real OmniRoute free-registry ingestion

## Why

Free-registry sync currently accepts a prebuilt registry payload only. It needs
to fetch the authoritative free-model registry from OmniRoute, validate schema
drift, and persist sync outcomes.

## What Changes

- Add a live fetch of the OmniRoute free-model registry (and free-provider
  rankings) via the management API with auth and bounded retries.
- Validate upstream schema drift and report it instead of silently dropping
  fields; persist the sync outcome (counts, drift, errors).

## Impact

- Affected specs: `free-provider-registry-sync`
- Affected code (later): `src/fmo/registry.py`, `src/fmo/omniroute.py`
- Spec-only proposal; no implementation in this change.
