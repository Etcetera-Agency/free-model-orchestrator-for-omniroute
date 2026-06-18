# Change: Add persistence repository layer

## Why

`data-model` declares PostgreSQL as the single store, but `src/fmo/db.py` only
applies the schema and lists table names. No pipeline stage reads or writes the
database it is specified against, so there is no place for run state to live
between stages. A typed repository layer is the prerequisite for wiring the
pipeline (`add-pipeline-orchestration`) and for run-lock persistence
(`add-runtime-bootstrap-and-locks`).

## What Changes

- Add `src/fmo/persistence.py`: a connection/transaction manager built from
  `DATABASE_URL` plus repository functions for the domain tables in
  `reference/db/schema.sql` (provider_endpoints, quota rules, probes, scores,
  combos/plans, snapshots, audit, runs).
- Persist every external fetch as an immutable content-hashed snapshot, per the
  project convention.
- Expose explicit transaction boundaries so a stage either commits its writes
  atomically or leaves no partial state.
- Repository writes are idempotent on their stage idempotency key.

## Impact

- Affected specs: `persistence` (new capability), `data-model` (ADDED repository
  requirement).
- Affected code: new `src/fmo/persistence.py`; `src/fmo/db.py` reuse for schema;
  callers added later by `add-pipeline-orchestration`.
- Tests use a real ephemeral PostgreSQL (no mock DB), per `project.md`.
