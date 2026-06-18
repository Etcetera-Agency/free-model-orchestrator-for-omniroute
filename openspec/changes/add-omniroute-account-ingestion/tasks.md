## 1. Live connection/account fetch

- [ ] 1.1 Failing test: account discovery fetches connections and rate-limit
  availability from OmniRoute with auth before grouping pools.
- [ ] 1.2 Failing test: a failed rate-limit fetch is treated conservatively
  (connections not promoted to independent capacity).
- [ ] 1.3 Implement the live fetch with bounded retries and structured errors.

## 2. Fixtures

- [ ] 2.1 Record realistic OmniRoute connection/rate-limit fixtures and tests.

## 3. Validation

- [ ] 3.1 `openspec validate add-omniroute-account-ingestion --strict` passes.
