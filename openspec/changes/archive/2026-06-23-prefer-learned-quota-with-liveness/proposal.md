# Change: Gate apply on live liveness; treat learned limits as a reactive rate

## Why

The apply gate is misaligned with how OmniRoute actually reports quota, so in
production it would reject almost every free endpoint and leave combos empty.

`GET /api/usage/quota` derives `quotaTotal`/`quotaUsed`/`resetAt` from OmniRoute's
**learned limits** (`src/app/api/usage/quota/route.ts` →
`open-sse/services/rateLimitManager.ts`):

- The learned `limit`/`remaining` come from the `x-ratelimit-*-requests`
  (or `anthropic-ratelimit-requests-*`) headers — they are **request counts for a
  sub-day rate window** (the manager computes `minTime = 60000 / limit`, i.e. a
  per-minute rate), **not tokens and not a daily budget**. `resetAt` is the rate
  window reset (`rateLimitedUntil`).
- `quotaTotal` is non-null only after OmniRoute has *learned* the rate from real
  429s/headers. A healthy idle free provider reports `quotaTotal: null`,
  `quotaUsed: 0`, `percentRemaining: 100`, `resetAt: null`.
- `resetAt` is set **only while the connection is currently rate-limited**, so
  `resetAt: null` is the healthy state, not missing data.

Two consequences:

1. The current gate `_endpoint_quota_row_is_safe` requires an absolute live
   remaining and a **future** `reset_at`. Both invert OmniRoute's model: a healthy
   free endpoint has no learned rate yet and `resetAt: null`, so it is rejected
   *because it is not rate-limited*. Even a learned endpoint is rejected solely on
   the `reset_at` clause when it is not currently limited.
2. `quota_manager._normalize_quota` reads `quotaTotal`/`quotaUsed` into
   `limit_tokens` and divides by `tokens_per_request` — it treats a **request
   rate as tokens** (`60 req/min ÷ 2000 ≈ 0.03`). The quota-manager spec repeats
   the same error ("treated as the tokens axis it is"). This is latent because the
   captured fixture has `quotaTotal: null` everywhere.

Per our own model — `quota_normalize` keeps request budgets in
request-equivalents/day but **sub-day request rates stay reactive** (see the
`Sub-day request rates are reactive, not budget rules` requirement) — the learned
limit belongs to the **reactive** side: it feeds liveness/lockout and OmniRoute's
runtime enforcement, **not** the daily budget. The daily budget for the forecast
stays sourced from research and no-auth calibration.

## What Changes

- Capture `percentRemaining` and lockout (`resetAt` in the future) from
  `GET /api/usage/quota` as a live **liveness** signal.
- Treat learned `quotaTotal`/`quotaUsed` as **request counts for a sub-day
  reactive rate** (liveness + OmniRoute-enforced gate), **not** a token axis and
  **not** a daily-budget capacity. Fix `_normalize_quota` to stop dividing the
  request rate by `tokens_per_request`, and correct the quota-manager wording.
- Keep the **daily budget** (forecast/allocation capacity, request-equivalents
  per day) sourced from research and no-auth calibration axes only.
- **BREAKING** (apply-gate semantics): redefine `quota_safe`. An endpoint is
  apply-safe when it is confirmed-free, hard-stop-capable, has a fresh passing
  probe, has a **known daily budget** (research/calibration capacity above the
  configured safety buffer), and a **fresh live liveness** signal showing
  `percentRemaining` above the configured floor and not currently locked out. Drop
  the `reset_at is not None and reset_at > now` requirement; a future `resetAt`
  now means *locked out → excluded*, not *required*.

## Impact

- Affected specs: `quota-manager`, `combo-applier`
- Affected code: `src/fmo/quota_manager.py` (`_normalize_quota`, `LiveQuota` —
  add `percent_remaining`, `locked_out`; stop treating `quotaTotal` as tokens),
  `src/fmo/composition_stages.py` (`_quota_sync_stage` persistence,
  `_endpoint_quota_row_is_safe`, daily-budget capacity from research/calibration),
  `src/fmo/config.py` (`APPLY_MIN_PERCENT_REMAINING`).
