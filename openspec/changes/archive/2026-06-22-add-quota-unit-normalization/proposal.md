# Change: Unify quota to request-equivalents per day

## Why

Free-tier quota data is heterogeneous: some endpoints expose only a token budget
(OmniRoute `quotaTotal`/`monthlyTokens`), but **often only a request limit is
known** (RPD from quota research). The original code collapsed both into a single
dimensionless `limit`, so `effective_remaining`, attribution and allocation
silently mixed tokens and requests in `min()`/`+` — arithmetically meaningless.

Forecast needs one comparable **magnitude** to rank model placement (fractions
cannot rank a 1k vs a 1M endpoint), and demand is natively in requests
(`forecast.aggregate_demand` counts calls). The common unit is therefore
**request-equivalents per day**, and token budgets are converted into it.

This change is the foundation the other quota slices already depend on
(`update-quota-research-capture-axis`, `update-quota-manager-binding-capacity`,
`add-weekly-tpr-recalibration` all reference it). It defines the unit, the
conversion and its inputs so nothing is a dangling "landed" reference.

## What Changes

- Add the pure conversion module `src/fmo/quota_normalize.py` *(landed)*:
  - `to_requests_per_day(metric, window, amount, tokens_per_request)` — `requests`
    day/month pass through (month `/30`); `tokens` day/month are divided by the
    factor; sub-day windows (`minute`/`hour`) return `None` as reactive rate gates
    policed by OmniRoute.
  - `binding_capacity(axes, tokens_per_request)` — converts an endpoint's
    `(metric, window, amount)` axes and returns the tightest in req/day, or `None`
    when no budget axis is known.
- Add config `tokens_per_request` (default `2000`, validated `> 0`) — the flat
  token-to-request conversion factor *(landed)*. It is a global averaged constant;
  per-provider factors are explicitly out of scope.
- Capture **token usage** in telemetry so the factor has a real-world input: the
  telemetry model SHALL record token counts per provider/model from
  `GET /api/usage/analytics` alongside the existing request counts. This is the
  observed-tokens / observed-requests source that the weekly recalibration
  (`add-weekly-tpr-recalibration`) consumes; today `TelemetryMetric` reads only
  `requests`.

## Impact

- Affected specs: `quota-manager` (the req/day unit + conversion + factor),
  `telemetry-sync` (token capture).
- Affected code: `src/fmo/quota_normalize.py` *(landed)*, `src/fmo/config.py`
  (`tokens_per_request` + validation, *landed*), `src/fmo/telemetry.py`
  (`TelemetryMetric.tokens` + parse), `tests/test_quota_normalize.py` *(landed)*.
- Pure conversion, no new external calls. RPM stays reactive. The allocator and
  forecast keep consuming a single scalar capacity — now in request-equivalents
  per day.
