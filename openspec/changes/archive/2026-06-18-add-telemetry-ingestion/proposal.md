# Change: Real telemetry ingestion

## Why

Telemetry sync currently normalizes caller-provided telemetry payloads only. It
needs to fetch real usage, latency, failure and trace data from OmniRoute/runtime
logs or Hermes session stores.

## What Changes

- Add a live fetch of usage/latency/failure telemetry from OmniRoute
  `GET /api/usage/analytics` (and `GET /api/usage/call-logs` for failures/traces)
  and/or the Hermes `state.db` sessions store, with auth and bounded retries.
- Normalize the fetched real shapes into the existing telemetry model; fail
  conservatively when a source is unavailable.
- Record realistic telemetry fixtures for deterministic tests of this boundary.

## Impact

- Affected specs: `telemetry-sync`
- Affected code (later): `src/fmo/telemetry.py`
- Spec-only proposal; no implementation in this change.
