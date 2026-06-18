# Change: Finish Hermes inventory adapters and live enumeration

## Why

The real Hermes source-shape parsers landed in `add-hermes-inventory-real-shapes`.
What remains is the adapter/enumeration surface: command and http inventory
adapters, live profile enumeration, and `service` consumers from gateway config.

## What Changes

- Add command and http Hermes inventory adapters that return the real source
  shapes with structured errors (in addition to the filesystem reader).
- Enumerate profiles live by scanning real profile dirs + `config.yaml` model
  (instead of a caller-supplied listing).
- Derive `service` consumers from the enabled Hermes gateway platforms config.
- Capture inventory fixtures from a live Hermes deployment where feasible.

## Impact

- Affected specs: `hermes-inventory`
- Affected code (later): `src/fmo/hermes_inventory.py`
- Spec-only proposal; no implementation in this change.
