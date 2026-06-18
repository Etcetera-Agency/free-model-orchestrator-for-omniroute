## 1. Production search client

- [ ] 1.1 Failing test: quota research calls OmniRoute `/v1/search` with
  `gemini-grounded-search` and configured auth, persisting the snapshot.
- [ ] 1.2 Failing test: an unavailable search source fails conservatively (no
  fabricated quota rule).
- [ ] 1.3 Implement the live client, retries, persistence and structured
  extraction over the real result.

## 2. Fixtures

- [ ] 2.1 Record realistic `/v1/search` response fixtures and tests.

## 3. Validation

- [ ] 3.1 `openspec validate add-quota-research-ingestion --strict` passes.
