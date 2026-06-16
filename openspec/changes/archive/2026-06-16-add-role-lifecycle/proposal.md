# add-role-lifecycle

## Why

Hermes roles are not static. The orchestrator must keep an accurate registry of
which profiles/routines consume each role and how often, refresh forecasts when
consumption changes, and manage role creation/retirement safely so a role that
disappears for one scan is not deleted. Source:
`reference/docs/modules/23`, `reference/docs/architecture/03`.

## What Changes

- Add `hermes-inventory`: daily full inventory, unknown-role immediate full
  inventory, consumer registry, filesystem/command/http adapters, forecast
  refresh on change, Inspector scope limits.
- Add `dynamic-role-lifecycle`: reconcile desired role set, create/update/retire
  with grace period and zero-use guard, new-role bootstrap.

## Impact

- New specs: `hermes-inventory`, `dynamic-role-lifecycle`.
- Depends on: `add-foundation`, `add-allocation` (forecast + combos).
- Drives the demand model and the active role set for allocation.
