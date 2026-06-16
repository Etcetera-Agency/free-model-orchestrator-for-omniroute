# add-quota

## Why

The core invariant — never exceed confirmed free capacity — is enforced here.
This phase researches quota where OmniRoute does not provide it, classifies
whether an endpoint is free-usable right now, attributes usage to capacity
groups when no `quota_pool` is known, and tracks effective remaining with hard
stops. Source: `reference/docs/modules/03,04,08`,
`reference/docs/architecture/09`.

## What Changes

- Add `quota-research`: Instructor-based inspector using OmniRoute
  `gemini-grounded-search`; summary-sourced activation with capped confidence.
- Add `access-classifier`: ordered free/exclusion classification, trust order,
  fail-closed.
- Add `quota-attribution`: `quota_attribution_group` with the canonical status
  set, capacity-by-status, merge/split, no-auth scopes.
- Add `quota-manager`: effective-remaining counter, hard-stop gating, reservation
  for own probes only, reset handling, role budgets, historical-reserve guard.

## Impact

- New specs: `quota-research`, `access-classifier`, `quota-attribution`,
  `quota-manager`.
- Depends on: `add-foundation`, `add-discovery`.
- Feeds: scoring, allocation.
