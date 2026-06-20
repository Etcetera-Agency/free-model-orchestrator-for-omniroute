## 1. Persist metadata sync output

- [x] 1.1 Failing test: `sync-metadata` persists models.dev candidates and the AA snapshot through the repository
- [x] 1.2 Implement persistence of `MetadataSyncResult` (consume the return value instead of discarding it)
- [x] 1.3 Failing test: `--dry-run` fetches/validates but persists nothing

## 2. Wire into the pipeline

- [x] 2.1 Failing test: the `external-metadata-sync` stage of `full` records external metadata before discovery and scoring read it
- [x] 2.2 Implement the persisting metadata stage in the canonical stage list

## 3. Validation

- [x] 3.1 Run targeted pytest for `tests/test_external_metadata.py` and `tests/test_cli.py`
- [x] 3.2 Run full `pytest -q`
- [x] 3.3 `openspec validate persist-metadata-sync --strict`
