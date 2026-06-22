# Change: Quota manager expresses capacity in request-equivalents per day

## Why

Capacity is unified to **request-equivalents per day** so demand (natively calls)
and capacity compare on one scale
([src/fmo/quota_normalize.py](../../../src/fmo/quota_normalize.py)). The producers
already speak in typed axes — research captures `requests`/`tokens` claims, the
no-auth calibration emits a `tokens` rule, and OmniRoute live quota
(`quotaTotal`/`monthlyTokens`) is a token budget.

The quota manager is still the missing consumer. `effective_remaining`
([src/fmo/quota_manager.py](../../../src/fmo/quota_manager.py)) and the live-quota
fetch treat `limit`/`remaining` as a single dimensionless scalar with no unit, so:

- a token budget and a request limit can be `min()`-ed together as if they shared
  a unit, and
- `effective_remaining` is returned in whatever raw unit the source happened to
  use, not a comparable one.

This slice makes the quota manager convert every endpoint's axes through
`binding_capacity` into request-equivalents per day before computing remaining, so
the allocator and forecast receive one comparable magnitude.

## What Changes

- The quota manager SHALL assemble each endpoint's known budget axes
  `(metric, window, amount)` from all of its sources — research rule, no-auth
  calibration rule, and live quota — and convert them with `binding_capacity`
  (factor `tokens_per_request`) into a single capacity in request-equivalents per
  day, bound by the tightest axis. Sub-day request windows are excluded (reactive).
- Live quota (`GET /api/usage/quota`, `quotaTotal`/`quotaUsed`) SHALL be treated as
  the `tokens` axis it is, and its limit/used converted to req/day via the factor;
  `remaining` SHALL be derived in the same unit.
- `effective_remaining` SHALL compute remaining in request-equivalents per day from
  the converted limit, provider-reported remaining, local usage, pending
  reservations and safety buffer. The existing semantics are preserved: unknown
  when every source is unknown, and a negative result is kept.
- The no-auth calibration rule SHALL be included in the endpoint's axis list, not
  only research and live, so self-calibrated endpoints contribute their converted
  capacity.
- Hard-stop gating, reservation-only-for-probes, reset/reclassify and the
  historical-reserve guard are unchanged.

## Impact

- Affected specs: `quota-manager`.
- Affected code: `src/fmo/quota_manager.py` (`effective_remaining`,
  `_normalize_quota`/live conversion, axis assembly across sources), `tests/`.
- The allocator and forecast are not changed structurally — they keep consuming a
  single scalar capacity, now in request-equivalents per day.
- No new external calls; conversion uses the already-configured
  `tokens_per_request` factor.
