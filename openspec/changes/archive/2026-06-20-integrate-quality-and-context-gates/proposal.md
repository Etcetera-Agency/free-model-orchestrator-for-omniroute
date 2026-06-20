# integrate-quality-and-context-gates

## Why

Two specified hard-filter capabilities are implemented as pure functions and
unit-tested, but never called by the production scoring stage:

- `context-window-eligibility` (`src/fmo/context.py`: `effective_context_window`,
  `context_eligible`) — effective context = min of known sources; below the role
  minimum the endpoint is excluded; unknown excluded unless override.
- `quality-gate` (`src/fmo/quality.py`: `evaluate_quality_gate`) — at most one
  minimum quality gate per role applied as a hard pre-filter; unverifiable
  excluded unless override; index-version binding keeps the current combo on a
  major index change.

The production `role-scoring` stage (`composition_stages.py::_role_scoring_stage`)
filters only through `scoring.eligible_for_scoring`, which checks access, probe,
quota, match, breaker, and capabilities — **not** context window or the quality
gate. `_role_scoring_stage` does not import `context` or `quality` at all. So both
hard filters are inert in the real pipeline: endpoints below a role's context
minimum or quality gate can still be scored and allocated.

The executable-spec gate is green only because the `context-window-eligibility`
and `quality-gate` scenarios are bound to isolated unit tests of the pure
functions, not to the integrated scoring path — green tests are masking a missing
integration.

## What Changes

- Call `context_eligible` (over `effective_context_window` of the endpoint's
  known context sources) inside the production scoring eligibility path, before
  weighted scoring, honoring the per-role minimum and `manual_override`.
- Call `evaluate_quality_gate` for the role's optional single gate inside the
  same path: exclude below-gate and unverifiable (unless
  `allow_unverified_quality_gate`), and on an index-version mismatch keep the
  current combo (do not apply a new plan).
- Persist the rejection reason / gate status so `explain-endpoint` reports
  context/quality exclusions with their real cause.
- Add integration-level scenarios binding these gates to the production scoring
  stage (not only the pure functions).

## Impact

- Modified specs: `role-scorer` (Eligibility filter precedes scoring),
  `pipeline-orchestration` (Scoring stage applies context and quality hard
  filters).
- Affected code: `src/fmo/composition_stages.py::_role_scoring_stage`,
  `src/fmo/scoring.py` (eligibility wiring), reuse of `src/fmo/context.py` and
  `src/fmo/quality.py`.
- No new external dependency; AA index version already persisted.
- Risk: tightens eligibility — endpoints previously allocated despite small
  context / below quality gate will now be excluded (intended).
