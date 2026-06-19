## Context

Run locks are stored as `sync_runs` rows with:

- `run_type = 'lock'`
- `trigger = <logical lock name>`
- `status = 'held'`
- `finished_at IS NULL`

The scheduler uses those locks to prevent overlapping daily runs, provider
scans, and combo applies. Current acquisition is not atomic because it does:

1. `SELECT` active lock row.
2. If absent, `INSERT` active lock row.

Two transactions can interleave between those steps.

## Goals

- Make lock acquisition race-safe across independent processes and connections.
- Preserve the current row-backed lock audit trail.
- Keep release behavior explicit and idempotent.
- Cover both fresh schema and upgrade migration paths.

## Non-Goals

- Do not add a new lock table.
- Do not switch to connection-scoped advisory locks.
- Do not change scheduler trigger semantics.
- Do not change lock names or run result status mapping.

## Decision

Use a PostgreSQL partial unique index on active lock rows:

```sql
CREATE UNIQUE INDEX sync_runs_active_lock_name_idx
ON sync_runs (trigger)
WHERE run_type = 'lock'
  AND status = 'held'
  AND finished_at IS NULL;
```

Then acquire with one insert:

```sql
INSERT INTO sync_runs (run_type, trigger, status, code_version, config_hash)
VALUES ('lock', %(name)s, 'held', 'lock', %(name)s)
ON CONFLICT (trigger)
WHERE run_type = 'lock'
  AND status = 'held'
  AND finished_at IS NULL
DO NOTHING
RETURNING id;
```

If a row returns, the caller acquired the lock. If no row returns, another
process already holds it.

## Risks / Trade-Offs

- A partial unique index requires a migration for existing deployments. Mitigate
  by adding a migration before implementation and validating with the migration
  runner.
- Existing duplicate active lock rows would block index creation. Mitigate by
  documenting that the migration targets healthy state; implementation can fail
  fast rather than silently deleting active lock rows.

## Migration Plan

1. Add the partial unique index to `reference/db/schema.sql`.
2. Add an ordered migration creating the same index for existing databases.
3. Change repository acquisition to use atomic insert.
4. Add a real PostgreSQL concurrency test that opens two transactions and proves
   only one active lock can be acquired.
