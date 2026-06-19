# Change: Persist external metadata sync output

## Why

`sync_external_metadata` fetches models.dev free candidates and the Artificial
Analysis snapshot and returns a `MetadataSyncResult`, but `run_cli` calls
`sync(dry_run=args.dry_run)` and **discards the return value**. The one live
production side-effect (`sync-metadata` / the metadata stage of `full`) therefore
writes nothing to the database, leaving downstream discovery and role scoring
with no persisted external metadata to read. The `telemetry-sync::Daily sync
before scoring` ordering guarantee is meaningless if the synced metadata is
never stored.

## What Changes

- Persist the metadata-sync output through the repository layer inside the
  `external-metadata-sync` stage: store models.dev free candidates and the AA
  snapshot keyed for downstream lookup.
- Respect `--dry-run`: validate and fetch but persist nothing.
- Wire the persisting metadata stage into the canonical stage list built by
  `compose-production-pipeline` so `full` actually records external metadata
  before discovery and scoring.

## Impact

- Affected specs: `persistence` (ADDED: external metadata persisted for
  downstream stages).
- Affected code: `src/fmo/metadata_sync.py`, `src/fmo/cli.py` (consume the
  result), repository layer.
- Depends on `add-persistence-repositories`, `compose-production-pipeline`.
