# add-web-cookie-and-cli

## Why

Two operational slices: allow web-cookie providers into combos as constrained
fallbacks without auto-discovering their catalogs, and provide the operator CLI
with safe exit codes and diagnostics. Source: `reference/docs/modules/19,16`.

## What Changes

- Add `web-cookie-candidates`: manual/static endpoints only, capability-gated
  role eligibility, basic-text probe, fallback-only with limited weight, unknown
  quota not guaranteed, daily session health.
- Add `cli-and-operations`: command set, flags, diagnostics, exit codes, and the
  local dry-run that never calls `/api/combos/test`.

## Impact

- New specs: `web-cookie-candidates`, `cli-and-operations`.
- Depends on: scoring and allocation (eligibility + combos), foundation (client).
