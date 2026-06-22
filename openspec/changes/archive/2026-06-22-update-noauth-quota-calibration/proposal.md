# Change: Document no-auth quota calibration

## Why

Some OmniRoute no-auth providers expose the same models and quota pool as an
authenticated sibling provider. Example: `opencode` should inherit its quota and
model expectations from `opencode-zen`.

Other no-auth providers do not expose a reliable quota source. For those, FMO
must treat the quota as unknown until an operator places the provider at the
front of a combo, observes token usage in OmniRoute, and records the calibrated
quota. Without this documented path, unknown no-auth capacity can be guessed or
left untracked.

## What Changes

- Add quota-research requirements for no-auth providers that alias an auth
  sibling quota/model pool.
- Add quota-research requirements for manual calibration of no-auth providers
  whose quota cannot be determined from registry, live quota, or search.
- Document the operator-first combo placement and OmniRoute token-usage
  observation flow before any calibrated quota is promoted to usable capacity.

## Impact

- Affected specs: `quota-research`
- Affected docs/workflow: `openspec/TODO.md` tracks the live calibration follow-up
- Affected code: future implementation may touch quota research, allocation
  ordering, quota attribution, and operator tooling, but this change only
  documents the slice
