## 1. Oracles

- [ ] 1.1 Write failing test: probing, telemetry, inventory, and role stages
      resolve unchanged through the adapter table and live in dedicated modules,
      bound to `system-architecture::Probing, telemetry, inventory, and role
      stages live in dedicated modules`.
- [ ] 1.2 Write failing test: the role-scoring helper cluster
      (health/stability/latency components, quality-band seeding, AA/health
      lookups) lives in the role module, not in the package root, bound to
      `system-architecture::Role scoring helpers move with the role stage`.

## 2. Extract the clusters

- [ ] 2.1 Move `_probing_stage` into `probing.py`.
- [ ] 2.2 Move `_telemetry_sync_stage` into `telemetry.py`.
- [ ] 2.3 Move the Hermes inventory stage + helpers into `inventory.py`.
- [ ] 2.4 Move the role lifecycle + scoring stages and their helper cluster into
      `roles.py`, importing shared helpers from the package root unchanged.
- [ ] 2.5 Fix the pyright errors in the moved modules.

## 3. Close out

- [ ] 3.1 `make check` clean.
- [ ] 3.2 Run the role/telemetry/inventory test files then the full suite; it
      passes unchanged.
- [ ] 3.3 Remove the two bound scenarios from `tests/spec_coverage_pending.txt`
      and `EXPECTED_ACTIVE_PENDING`.
- [ ] 3.4 `openspec validate refactor-split-stages-runtime --strict`.
