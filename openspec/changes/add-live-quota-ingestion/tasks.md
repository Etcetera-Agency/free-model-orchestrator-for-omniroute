## 1. Live quota fetch

- [ ] 1.1 Failing test: quota reset/reclassification fetches live quota from the
  configured provider/OmniRoute source with auth.
- [ ] 1.2 Failing test: a stale or unavailable quota source fails closed (no
  usable capacity inferred).
- [ ] 1.3 Implement the fetchers with bounded retries and stale-data handling.

## 2. Fixtures

- [ ] 2.1 Record realistic quota-source fixtures and add unavailable-source tests.

## 3. Validation

- [ ] 3.1 `openspec validate add-live-quota-ingestion --strict` passes.
