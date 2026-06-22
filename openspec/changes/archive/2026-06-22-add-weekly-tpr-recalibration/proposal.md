# Change: Weekly recalibration of the global tokens-per-request factor

## Why

Heterogeneous free-tier quota is unified to one comparable unit — **request-
equivalents per day** — so demand (natively calls) and capacity compare on one
scale. Token budgets are converted with a flat factor
`tokens_per_request` (default `2000`,
[src/fmo/quota_normalize.py](../../../src/fmo/quota_normalize.py)).

That constant is a guess. Two endpoints' real token-per-request size differs from
`2000`, so every endpoint whose capacity we **derived ourselves** — from a search
summary (`summary`) or from self-calculated calibration (`calibrated`) — inherits
that guess. Live-quota endpoints read an authoritative `quotaTotal` and do not
depend on the factor, so they are not affected.

The no-auth calibration module
([`promote_noauth_calibration`](../../../src/fmo/quota_research.py)) already
observes real `observed_tokens` and `observed_requests` while probing unknown
providers. Over a week it accumulates enough samples to compute the **actual**
average tokens-per-request and replace the guess — and, from the refined factor,
recompute every self-derived endpoint's capacity. Nothing runs that loop today:
the factor stays `2000` forever and the derived numbers never improve.

This slice adds a **weekly** job that refines the single global factor from
accumulated calibration observations and recomputes only the derived endpoints.
It does NOT touch the daily pipeline cadence and does NOT introduce per-provider
factors (one global averaged number, as decided).

## What Changes

- Add config `tokens_per_request_recalibration_cron` (default `"0 5 * * 0"` —
  Sundays 05:00), validated as a 5-field cron. Already added in
  [src/fmo/config.py](../../../src/fmo/config.py).
- The pure refinement logic already exists in `quota_normalize.py`:
  `refine_global_tokens_per_request(observations, current, min_total_requests=100,
  max_change_ratio=0.5)` aggregates observed tokens/requests into a new global
  factor, keeps `current` when there is too little signal (`< min_total_requests`),
  and clamps the result to within `±max_change_ratio` of `current` so one noisy
  week cannot swing the factor every derived endpoint depends on;
  `recompute_derived_capacities(endpoints, tokens_per_request)` recomputes req/day
  capacity only for endpoints whose source is in `DERIVED_SOURCES =
  {"summary", "calibrated"}`.
- Add the **job that wires this to the weekly cron**: on a matching tick it loads
  the accumulated calibration observations and the current factor, calls
  `refine_global_tokens_per_request`, persists the new factor, then calls
  `recompute_derived_capacities` over all `summary`/`calibrated` endpoints and
  persists the recomputed capacities. Authoritative `live` endpoints are left
  untouched. The job holds a run lock so it cannot overlap itself or a daily run.
- The factor refinement and the derived recompute SHALL be a single transactional
  step: the persisted factor and the persisted derived capacities are always
  consistent with each other.

## Impact

- Affected specs: `quota-manager` (factor refinement + derived recompute),
  `scheduler` (weekly recalibration cadence + lock).
- Affected code: `src/fmo/quota_normalize.py` (refine + recompute — landed),
  `src/fmo/config.py` (cron setting — landed), a new weekly recalibration job
  wired into the scheduler, its persistence (read observations + current factor,
  write factor + derived capacities), `tests/`.
- No new external network calls (observations come from already-collected
  calibration/telemetry data). The daily pipeline cadence is unchanged. Live-quota
  endpoints are never recomputed.
