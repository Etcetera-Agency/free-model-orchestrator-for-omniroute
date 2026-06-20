# Change: Migrate discovery writers to repository

## Why

Review found the remaining direct SQL writers in `src/fmo/scanner.py` and
`src/fmo/registry.py`. The living persistence spec requires pipeline stages to
write through repository functions instead of embedding table SQL.

The direct writers also make production stage wiring harder because discovery
and registry stages cannot share a single repository transaction boundary or
repository-level idempotency behavior.

## What Changes

- Add repository methods for provider catalog snapshots, provider/account
  upserts used by discovery, free provider registry snapshots, and free model
  definition upserts.
- Refactor `CatalogScanner` and registry persistence to accept repository or
  transaction dependencies instead of opening their own direct psycopg
  connections.
- Update tests so scanner/registry persistence fails if table SQL remains in the
  stage modules.
- Clean up `openspec/TODO.md` contradiction while keeping any still-deferred
  work visible.

## Impact

- Affected specs: `persistence`, `provider-scanner`,
  `free-provider-registry-sync`, `runtime-documentation`.
- Affected code: `src/fmo/scanner.py`, `src/fmo/registry.py`,
  `src/fmo/persistence.py`, tests under `tests/`, `openspec/TODO.md`,
  `completion.review`.
- No DB schema change expected; work uses existing tables in
  `reference/db/schema.sql`.
