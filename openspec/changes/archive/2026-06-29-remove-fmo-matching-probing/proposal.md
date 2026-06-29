# Change: Remove FMO model matching, probing, and final cleanup

## Why

Final cutover slice. OmniRoute owns model intelligence (`model_intelligence` resolved
by source precedence) and learns real outcomes from the request path, so FMO's model
matcher and probe runner are obsolete. This slice also folds in the remaining
schema/config/module cleanup that turns FMO into a publisher-only service.

Depends on `add-pool-spec-publisher` and OmniRoute `add-fmo-pools-planning` live.

Concept: `FMO_SIDE_IMPLEMENTATION.md` §3.1 (reuse map), §12.

## What Changes

- **Remove** the `model-matcher` capability — OmniRoute owns matching + score
  normalization via `model_intelligence`.
- **Remove** the `probe-runner` capability — OmniRoute observes real traffic; the
  place-first calibration canary replaces probing-as-capacity.
- Delete `matcher.py`, `artificial_analysis.py`, `aa_migration.py`,
  `aa_index_runtime.py`, `scoring.py`, `probes.py`, plus the discovery set
  (`scanner.py`, `provider_sweep.py`, `candidates.py`, `model_registration.py`,
  `accounts.py`, `access.py`, `smart_review.py`, `web_cookie.py`).
- Trim `telemetry.py` (drop endpoint health/latency) and `state.py` (drop
  `ComboState`/`EndpointState`); shrink the schema to the demand/role/publish core.

## Impact

- **Removed capabilities**: `model-matcher`, `probe-runner` (the discovery/AA/telemetry
  modules retire in code under these two and the publisher's reuse map).
- **Config**: drop `llm_bootstrap_*`, `llm_smart_review_call_limit`.
- **Schema**: drop provider/model/endpoint/AA/free-definition/web-cookie tables.
- **Result**: FMO is publisher-only (`FMO_SIDE_IMPLEMENTATION.md` end state).
