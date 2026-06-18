# Change: Real OmniRoute account/connection ingestion

## Why

Account discovery currently groups caller-provided connection lists only. It
needs to fetch real connections, provider account status, pool membership and
rate-limit availability from OmniRoute so quota-pool grouping reflects live
state.

## What Changes

- Add a live fetch of OmniRoute connections (`/api/providers`), rate-limit
  availability (`/api/rate-limits`) and account/pool status via the management
  API with auth and bounded retries.
- Feed the fetched connections into quota-pool grouping; treat a failed
  rate-limit fetch conservatively (no false independence).

## Impact

- Affected specs: `account-discovery`
- Affected code (later): `src/fmo/accounts.py`, `src/fmo/omniroute.py`
- Spec-only proposal; no implementation in this change.
