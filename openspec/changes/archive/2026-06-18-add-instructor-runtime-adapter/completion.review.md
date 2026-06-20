# Completion Review: add-instructor-runtime-adapter

## Code Simplifier

- Removed a redundant advisory exception tuple, wrapped long site configs,
  made review/migration prompts deterministic JSON, and normalized malformed JSON
  repair failures to `LlmRuntimeError`.

## Verification

- `tests/test_instructor_runtime_adapter.py`, `tests/test_advisory.py`,
  `tests/test_role_lifecycle.py`, `tests/test_quota_research_ingestion.py`, and
  `tests/test_foundation.py` -> 72 passed, 1 skipped.
- `.venv/bin/python -m pytest -q` -> 195 passed, 7 skipped.
- `openspec validate add-instructor-runtime-adapter --strict` -> valid.
