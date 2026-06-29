# Change: Remove FMO quota research and quota management

## Why

Cutover slice. OmniRoute owns live quota, reset, cooldown, the quota source
precedence (incl. relocated search-research), and the request-equivalents algebra +
`tokens_per_request` learning. FMO's quota research and quota manager are now
duplicated guesses of request-path ground truth — remove them.

Depends on `add-pool-spec-publisher` and the OmniRoute planning slice
(`add-fmo-pools-planning`) owning quota + capacity.

Concept: `FMO_SIDE_IMPLEMENTATION.md` §12; `OMNI_FMO_FORK_REBALANCE_NOTES.md`
("Quota Ownership And Canary", "Capacity Unit Ownership").

## What Changes

- **Remove** the `quota-research` capability (primary source, search, instructor
  extraction, no-auth aliases/calibration, range resolution) — relocated to OmniRoute
  quota tiers 3/4.
- **Remove** the `quota-manager` capability (remaining counter, hard-stop, reset,
  live fetch, unit normalization, request-equivalents capacity, global-factor
  recalibration) — relocated to OmniRoute.
- Delete `quota_research.py`, `quota_manager.py`, `quota_normalize.py`,
  `quota_attribution.py`, `quota_recalibration.py`, the `composition_stages/quota.py`
  stage, and the `reference/prompts/quota-research.md` prompt.

## Impact

- **Removed capabilities**: `quota-research`, `quota-manager`.
- **Config**: drop `tokens_per_request`, `tokens_per_request_recalibration_cron`,
  `llm_quota_research_call_limit`.
- **Depends on**: `add-pool-spec-publisher` + OmniRoute `add-fmo-pools-planning` live.
