## 1. Capture liveness; treat learned limit as a reactive rate (fix unit bug)

- [x] 1.1 Write failing test: `_normalize_quota` captures `percentRemaining` and
      sets `locked_out` when `resetAt` is in the future, bound to
      `quota-manager::Percent-remaining and lockout captured from live quota`.
- [x] 1.2 Write failing test: learned `quotaTotal`/`quotaUsed` are captured as a
      sub-day request rate and are NOT divided by `tokens_per_request` nor added
      to the daily budget, bound to `quota-manager::Learned request limit captured
      as a reactive rate, not a daily budget`.
- [x] 1.3 Write failing test: an idle provider (`quotaTotal: null`,
      `percentRemaining: 100`) yields liveness but no learned rate, bound to
      `quota-manager::Idle provider yields liveness without an authoritative
      absolute`.
- [x] 1.4 Fix `_normalize_quota`/`LiveQuota`: add `percent_remaining`,
      `locked_out`; stop reading `quotaTotal` into `limit_tokens` /dividing by
      `tokens_per_request`; carry the learned value as a request rate.
      `_quota_sync_stage` persists liveness into the access-state evidence.

## 2. Daily budget excludes the live request rate (fix spec + axes)

- [x] 2.1 Write failing test: live `quotaTotal`/`quotaUsed` request counts are
      excluded from the binding daily budget (reactive rate gate), not converted
      as a token axis, bound to `quota-manager::Live quota requests do not
      contribute to the daily budget`.
- [x] 2.2 Update `endpoint_quota_axes`/`binding_capacity` usage so live quota is
      not added as a `tokens` axis; the daily budget comes from research and
      no-auth calibration only. (Living spec wording corrected by this change.)

## 3. Redefine the apply gate: research budget + live liveness

- [x] 3.1 Write failing test: a confirmed-free, hard-stop, freshly probed endpoint
      with a research/calibration daily budget above the buffer and healthy
      liveness passes, bound to `combo-applier::Research budget with healthy
      liveness passes`.
- [x] 3.2 Write failing test: an endpoint whose live `percentRemaining` is at/below
      the floor, or whose `resetAt` is in the future, is excluded, bound to
      `combo-applier::Exhausted or locked-out endpoint is excluded`.
- [x] 3.3 Write failing test: an endpoint with a known budget + healthy liveness
      and `resetAt = null` is not rejected on the reset clause, bound to
      `combo-applier::Endpoint with null reset is not rejected`.
- [x] 3.4 Add `APPLY_MIN_PERCENT_REMAINING` config (positive, validated) and
      rewrite `_endpoint_quota_row_is_safe`: require confirmed-free, hard-stop,
      fresh probe, known daily budget (research/calibration `>` safety buffer),
      fresh liveness with `percent_remaining > floor` and not locked out; drop the
      `reset_at > now` requirement. Daily-budget capacity for scoring/allocation
      stays research/calibration-derived.

## 4. Close out

- [x] 4.1 Run targeted tests (full `pytest` intentionally deferred by automation instruction; re-point any test markers orphaned by
      reworded living scenarios, e.g. the prior `Live token budget converted`).
- [x] 4.2 Remove the now-bound scenarios from `tests/spec_coverage_pending.txt`
      and `EXPECTED_ACTIVE_PENDING` in `tests/test_runtime_documentation.py`.
- [x] 4.3 `openspec validate prefer-learned-quota-with-liveness --strict`.
