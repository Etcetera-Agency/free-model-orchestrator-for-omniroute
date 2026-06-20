# Completion Review

- Entrypoint now derives `apply` preconditions from the repository-backed apply guard instead of passing a hardcoded `True`.
- Missing DB state, missing snapshots, invalid desired state, unsafe quota report, or missing/failed probes fail closed and block `apply` with exit 5.
- Healthy seeded guard inputs allow production `apply` dispatch through the composed runner.
- Verification: targeted bootstrap/CLI/allocation tests passed; full pytest passed; OpenSpec validation passed.
