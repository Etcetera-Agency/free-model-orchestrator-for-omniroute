## 1. Correct change-archive status

- [ ] 1.1 Fix `openspec/TODO.md`: `add-real-source-ingestion-tests` is archived, not active; note there are no active changes except slices 1–5
- [ ] 1.2 Keep the deferred scanner/registry → repository migration item accurate (and its two allowlist entries)

## 2. Refresh review and README

- [ ] 2.1 Rewrite `completion.review` to describe the current state and the slice plan
- [ ] 2.2 Update `README.md` to separate shipped component logic from production wiring delivered by slices 1–4

## 3. Validation

- [ ] 3.1 Validate the docs-alignment spec delta with `openspec validate align-docs-with-runtime --strict`
- [ ] 3.2 Run full `pytest -q` to confirm docs edits did not break the spec-coverage gate
