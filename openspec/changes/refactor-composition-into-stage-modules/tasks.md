## 1. Establish the behavior baseline

- [ ] 1.1 Confirm the full `pytest -q` suite is green before touching anything
      (this is the refactor's regression oracle)

## 2. Extract along existing seams

- [ ] 2.1 Extract the AA-index subcommand handlers into their own module
- [ ] 2.2 Extract the CLI dispatcher into its own module
- [ ] 2.3 Extract stage adapters grouped by domain (discovery/matching,
      access/quota, probe/telemetry, scoring/allocation/diff, apply/audit)
- [ ] 2.4 Extract shared helpers (smoke, current-combo reads, hashing)
- [ ] 2.5 Reduce `composition.py` to a thin wiring root

## 3. Prove behavior is unchanged

- [ ] 3.1 Full `pytest -q` passes unchanged (same tests, no new behavior tests)
- [ ] 3.2 `openspec validate refactor-composition-into-stage-modules --strict`
- [ ] 3.3 Add/bind a structural assertion test for the
      `Composition root stays within a single-responsibility boundary` scenario
      and shrink the pending list
