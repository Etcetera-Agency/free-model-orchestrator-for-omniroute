## 1. Live quota fetch

- [x] 1.1 Failing test: quota reset/reclassification fetches live quota from the
  configured provider/OmniRoute source with auth.
- [x] 1.2 Failing test: a stale or unavailable quota source fails closed (no
  usable capacity inferred).
- [x] 1.3 Implement the fetchers with bounded retries and stale-data handling.

## 2. Fixtures

- [x] 2.1 Record realistic quota-source fixtures and add unavailable-source tests.

## 3. Validation

- [x] 3.1 `openspec validate add-live-quota-ingestion --strict` passes.
