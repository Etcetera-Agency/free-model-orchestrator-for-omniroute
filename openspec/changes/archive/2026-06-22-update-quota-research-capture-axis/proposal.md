# Change: Quota research captures whichever axis it finds

## Why

Quota data is heterogeneous: a search summary may report a request limit
(`N requests/day`), a token budget (`N tokens/month`), or both. The deterministic
summary path collapses this into a single hardcoded axis:

- `extract_summary_claim` ([src/fmo/quota_research.py](../../../src/fmo/quota_research.py))
  always sets `metric="requests"`.
- `_extract_amount` only matches `\b\d+ requests?\b`.

So a summary that states a **token** budget either fails extraction
(`missing_amount`) or, worse, a token number is mislabelled as requests. Token
limits are silently lost, and request limits are forced even when the real
constraint is tokens. Downstream then mixes the two as if they were one unit.

Capacity is unified to **request-equivalents per day** via
`quota_normalize` (factor `tokens_per_request`); both `requests` and `tokens` are
first-class budget axes there. Research must therefore record **the axis it
actually found**, not a fixed one, so the normalizer can convert correctly.

Additionally, `requests/minute` (RPM) is a reactive rate gate policed by OmniRoute
(429 + Retry-After), not a planning budget. A research claim with a sub-day
request window MUST NOT be activated as a capacity rule.

## What Changes

- The deterministic summary extraction SHALL detect which axis the summary text
  expresses — `tokens` or `requests` — and set the claim `metric` accordingly,
  instead of hardcoding `requests`. When both are present, both axes SHALL be
  captured (the normalizer binds the tighter).
- Amount/window extraction SHALL support token phrasing (`N tokens per
  day/month`) in addition to request phrasing.
- A summary that expresses only a sub-day request rate (`requests/minute`,
  `requests/hour`) SHALL NOT produce a capacity rule; that axis is reactive and is
  left to OmniRoute. When that is the only signal, the endpoint stays without a
  confirmed budget rule (same conservative outcome as today's `missing_*`).
- The Instructor inspector path already returns `metric ∈ {requests, tokens}`; its
  output SHALL be carried through unchanged, and the same sub-day-request routing
  SHALL apply to inspector claims.
- The `summary_confidence_cap`, worsen-quota safe-mode, and deterministic
  validator remain the source of truth regardless of which axis was captured.

## Impact

- Affected specs: `quota-research`.
- Affected code: `src/fmo/quota_research.py` (`extract_summary_claim`,
  `_extract_amount`, `_extract_window`, sub-day-request routing), `tests/`.
- No change to the search surface, snapshot persistence, or confidence capping.
- Builds on the landed `quota_normalize` axis model; no behavioural change for
  endpoints that already only ever reported requests/day.
