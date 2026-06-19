## 1. Correct change-archive status

- [x] 1.1 Fix `openspec/TODO.md`: `add-real-source-ingestion-tests` is archived, not active; note implementation slices 1–4 are archived
- [x] 1.2 Keep the deferred scanner/registry → repository migration item and executable-spec allowlist status accurate

## 2. Refresh review and README

- [x] 2.1 Rewrite `completion.review` to describe the current state and the slice plan
- [x] 2.2 Update `README.md` to separate shipped component logic from production wiring delivered by slices 1–4

## 3. Validation

- [x] 3.1 Validate the docs-alignment spec delta with `openspec validate align-docs-with-runtime --strict`
- [x] 3.2 Run full `pytest -q` to confirm docs edits did not break the spec-coverage gate
