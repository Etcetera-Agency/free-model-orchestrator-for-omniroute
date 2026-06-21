# Implementation Tasks (TDD)

Write each test first (red) → green → refactor. PostgreSQL real. OmniRoute
`/api/usage/quota`, `/api/rate-limits`, `/v1/search` from recorded real shapes.

## Tasks

- [x] 1. TEST: with no free-model change since the prior run, quota research is
  skipped (idempotent no-change) and runs no `/v1/search` → implement the trigger
  gate (`should_run_quota_recalc`).
- [x] 2. TEST (trigger A): a new models.dev `free`/`0-cost` (or free-provider)
  model reachable via an existing connection triggers a full recalc that
  re-searches **all** endpoints → implement new-free detection + full-recalc.
- [x] 3. TEST (trigger B): an existing model whose free/0-cost status changed
  (free→paid or paid→free) triggers a full recalc → implement both-direction
  change detection (snapshot diff `gained`/`lost`).
- [x] 4. TEST: a new free model whose provider has **no** connection does NOT
  trigger recalc → implement reachability filter against `/api/rate-limits`.
- [x] 5. TEST: on recalc, an OmniRoute-known `quotaTotal` is used as the limit
  hint while search still sets hard-stop behaviour → implement OmniRoute-first
  cross-check in extraction.
- [x] 6. TEST: a model that gained free status is added to a fitting existing
  combo on rebalance; a model that lost free status is dropped and its quota rule
  deactivated (provider-model not deleted) → verify downstream end-to-end.
- [x] 7. (optional) Bulk extraction not required for current implementation;
  per-endpoint extraction remains acceptable for triggered recalc.
- [x] 8. Bind tests with `@pytest.mark.spec("...")`, drop matching lines from
  `tests/spec_coverage_pending.txt`, run full `pytest` and
  `openspec validate trigger-quota-recalc-on-free-model-changes --strict`.
