## 1. Live catalog fetch

- [ ] 1.1 Failing test: scanner fetches provider/model catalog from OmniRoute
  management API with auth before storing a snapshot.
- [ ] 1.2 Failing test: a fetch failure (network/non-200) records a failed
  snapshot and does not overwrite the previous catalog.
- [ ] 1.3 Implement the live fetch with bounded retries and structured errors.

## 2. Fixtures and snapshots

- [ ] 2.1 Record realistic OmniRoute catalog fixtures.
- [ ] 2.2 Snapshot integration tests over the recorded shapes.

## 3. Validation

- [ ] 3.1 `openspec validate add-omniroute-catalog-ingestion --strict` passes.
