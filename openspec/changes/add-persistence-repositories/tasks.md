## 1. Connection and transaction manager

- [ ] 1.1 Failing test: a transaction that raises mid-write leaves no rows (real ephemeral Postgres)
- [ ] 1.2 Implement `Database` wrapper over `psycopg` with `transaction()` context manager from `DATABASE_URL`
- [ ] 1.3 Failing test: committed transaction is visible to a new connection

## 2. Domain repositories

- [ ] 2.1 Failing tests: upsert + read round-trip for provider_endpoints, quota rules, probes, scores, combos/plans, audit
- [ ] 2.2 Implement repository functions for each domain table against `reference/db/schema.sql`
- [ ] 2.3 Failing test: repository writes keyed by stage idempotency key do not duplicate on re-run
- [ ] 2.4 Implement idempotent upsert keyed on the stage idempotency key

## 3. Snapshot store

- [ ] 3.1 Failing test: storing the same external payload twice yields one content-hashed snapshot row
- [ ] 3.2 Implement immutable content-hashed snapshot persistence

## 4. Validation

- [ ] 4.1 Run targeted pytest for `tests/test_persistence.py`
- [ ] 4.2 Run full `pytest -q`
- [ ] 4.3 `openspec validate add-persistence-repositories --strict`
