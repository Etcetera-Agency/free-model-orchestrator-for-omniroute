# Implementation Tasks (TDD)

Do tests first. Use injected fake HTTP clients. Do not call live models.dev or
Artificial Analysis in unit tests. Use isolated repo `.venv`. Do not run human
run. Do not run `check_scope_creep`.

## Tasks

- [x] 1. TEST: models.dev fetcher issues `GET https://models.dev/api.json`, returns parsed dict on HTTP 200 JSON object, and passes payload into `build_free_candidates`.
- [x] 2. TEST: models.dev fetcher fails deterministically on timeout/network error, non-200 response, invalid JSON, and missing/non-dict `providers`.
- [x] 3. IMPLEMENT: add models.dev HTTP fetch/sync functions with injected client/timeout and typed domain errors.
- [x] 4. TEST: Artificial Analysis fetcher requires configured API key, sends the key in the `x-api-key` header, and never exposes API key in errors/log-safe output.
- [x] 5. TEST: Artificial Analysis fetcher returns index version and normalized model metrics used by scoring: `intelligence_index`, `coding_index`, `agentic_index`, `median_output_tokens_per_second`, `median_end_to_end_seconds`.
- [x] 6. TEST: Artificial Analysis fetcher preserves missing metrics as missing, not zero, and rejects invalid payload shape.
- [x] 7. TEST: Artificial Analysis fetcher exposes new `index_version` to `detect_index_change` and keeps production unchanged when fetch fails.
- [x] 8. IMPLEMENT: add Artificial Analysis HTTP fetch/normalization functions with injected client/timeout, required API key, redacted error output, and typed domain errors.
- [x] 9. TEST: CLI/scheduler `sync-metadata` or `full` path calls models.dev sync before candidate discovery and authenticated AA sync before scoring/index migration.
- [x] 10. IMPLEMENT: wire fetchers into CLI/scheduler orchestration without live calls in tests.
- [x] 11. VALIDATE: run targeted tests, full `.venv/bin/python -m pytest -q`, and `openspec validate --all --strict`.
