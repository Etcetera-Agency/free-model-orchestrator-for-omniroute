# Status: IMPLEMENTED

Advisory LLM implemented with TDD in `tests/test_advisory.py`.

- Smart combo reviewer makes one structured advisory call, allowlists add/remove/move, rejects forbidden ops, applies valid diffs independently, and fails open without `/api/combos/test`.
- AA index migration detects version changes, freezes old thresholds, keeps current combos, stops production recalculation, selects strongest available model, validates proposals, and gates rollout on approval.
- No-model and invalid operational proposals leave production unchanged.

Verification:

- `.venv/bin/python -m pytest tests/test_advisory.py tests/test_role_lifecycle.py tests/test_allocation.py tests/test_scoring.py tests/test_quota.py tests/test_discovery.py tests/test_foundation.py -q`
- `openspec validate add-advisory-llm --strict`
