# Change: Cover Hermes inventory trigger behavior

## Why

The living `hermes-inventory` spec requires daily full inventory, allows explicit
manual/event-driven full inventory requests, and forbids unknown role names from
forcing immediate inventory or combo creation. That requirement currently lacks
acceptance scenarios, which weakens the executable-spec gate and hides trigger
behavior that should be tested before implementation/archive.

## What Changes

- Add acceptance scenarios for daily full inventory trigger behavior.
- Add acceptance scenarios for explicit manual full inventory requests.
- Add acceptance scenarios for the unknown-role event guard.

## Impact

- Affected specs: `hermes-inventory`
- Affected tests: future implementation must bind the new scenarios and remove
  matching entries from `tests/spec_coverage_pending.txt`
- Affected code: future tests may touch scheduler/composition trigger routing,
  but this slice only documents the missing scenarios
