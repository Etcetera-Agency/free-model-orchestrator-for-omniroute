# Completion Review

- Added `serve` CLI entrypoint with a real scheduler loop and `--run-once` bounded mode for tests/ops checks.
- Wired the composed scheduler to the canonical production runner and `HERMES_INVENTORY_CRON`.
- Verified cron, manual/event/urgent trigger routing through persistent locks, with no `/api/combos/test` calls.
- Scenario pending allowlist was already empty; scheduler scenarios are bound to executable tests.
- Verification: targeted scheduler/CLI/composition tests passed; full pytest passed; OpenSpec validation passed.
