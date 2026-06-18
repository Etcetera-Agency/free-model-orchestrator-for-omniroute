## 1. Live registry fetch

- [x] 1.1 Failing test: free-registry sync fetches the registry from OmniRoute
  with auth before building the registry.
- [x] 1.2 Failing test: schema drift in the registry payload is reported, not
  silently dropped.
- [x] 1.3 Implement the live fetch, drift validation, and outcome persistence.

## 2. Fixtures

- [x] 2.1 Record realistic OmniRoute free-registry/rankings fixtures and tests.

## 3. Validation

- [x] 3.1 `openspec validate add-omniroute-free-registry-ingestion --strict` passes.
