# Implementation Tasks

## 1. TDD Coverage

- [ ] 1.1 Add a failing test: `auto_router_tail` parses ordered entries with `id`
  and declared `input` modalities (default order `mimocode/mimo-auto` text,
  `kilo-auto/free` text, `openrouter/free` text+image); membership match is
  provider-flexible and case-insensitive; an unlisted model is not a router; the
  catalog parent `mcode/mimo-auto` is NOT treated as an alias of the configured
  child `mimocode/mimo-auto`.
- [ ] 1.2 Add a failing test: a router endpoint is NOT AA-scored — no
  `benchmark_fit` term and no missing-quality uncertainty penalty — while still
  being rejected by the non-quality hard filters when they fail.
- [ ] 1.3 Add a failing test: a router with a missing band metric is exempt from
  the quality gate — NOT excluded as `unverifiable` even with
  `allow_unverified_quality_gate` off — and never ordered as a scored member.
- [ ] 1.4 Add a failing test: in `build_priority_combo`, scored endpoints keep
  AA-quality-ascending order and qualifying routers are appended after the last
  scored endpoint in `auto_router_tail` order.
- [ ] 1.5 Add a failing test: a router whose config-declared `input` is text-only
  is skipped for a role requiring `image`, while one declaring `["text","image"]`
  is still appended; a router whose `effective_context_window` is below the role's
  context-window minimum is skipped by the existing context filter; routers
  failing the free access filter are skipped (catalog cost not trusted).
- [ ] 1.6 Add a failing test: routers do not consume the scored-slot
  `per_pool_cap`; the tail is bounded by `auto_router_tail` length.
- [ ] 1.7 Add a failing test: a role whose only eligible free endpoints are
  routers yields a valid router-only combo in config order (no paid fallback).
- [ ] 1.8 Bind scenarios with `@pytest.mark.spec(...)` and stage them in
  `tests/spec_coverage_pending.txt` until their tests land.

## 2. Implementation

- [ ] 2.1 Add the structured `auto_router_tail` setting (per-entry `id` +
  declared `input` modalities) and a provider-flexible
  `is_configured_router(model_id)` membership helper in `config.py`; match each
  entry on its own id, no parent/child collapsing. Context is not declared here.
- [ ] 2.2 In the scoring path, short-circuit AA scoring for configured routers:
  skip `aa_subscore`/`benchmark_fit` and emit no uncertainty penalty; keep all
  other non-quality eligibility hard filters.
- [ ] 2.3 In `quality.py`, exempt configured routers from the band/quality-gate:
  do not mark them `unverifiable` or exclude them on a missing band metric.
- [ ] 2.4 Carry router membership from the scoring stage into the score map that
  `build_priority_combo` consumes in `composition_stages.py`.
- [ ] 2.5 In `build_priority_combo`, build the scored head (AA ascending) then
  append the configured tail in config order, filtered per role by free access +
  config-declared `input` modalities covering role capabilities + the existing
  `effective_context_window` context-window hard filter + probe/quota/breaker;
  routers excluded from `per_pool_cap`.

## 3. Verification

- [ ] 3.1 Run targeted tests: config, scoring, quality, allocation, composition.
- [ ] 3.2 Run `.venv/bin/python -m pytest -q`.
- [ ] 3.3 Run `npx --yes @fission-ai/openspec@latest validate add-auto-router-fallback-tail --strict`.
- [ ] 3.4 Use Code Simplifier before finishing.
- [ ] 3.5 Update `completion.review` and shrink `tests/spec_coverage_pending.txt`.
