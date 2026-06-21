# trigger-quota-recalc-on-free-model-changes

## Why

Quota research (the `/v1/search` + Instructor extraction that learns a model's
quota **limit/policy**) is the only LLM-heavy stage. Today it runs over **every**
endpoint **every** run (`_quota_research_stage`, `src/fmo/composition_stages.py`
selects all `provider_endpoints WHERE canonical_model_id IS NOT NULL` with no
filter). That both wastes the selected free model's quota and contradicts the
living `quota-research` spec, which already states:

- *Primary quota source where OmniRoute is silent* — research is for endpoints
  **not** covered by an official API or OmniRoute; and
- *It SHALL NOT re-search daily an endpoint whose free access is already confirmed
  and whose rule is not stale.*

OmniRoute already exposes a per-connection quota where it knows it:
`GET /api/usage/quota` returns `quotaTotal` (a number when known, `null` when
not) and `resetAt` per connection. So the limit is known for some endpoints and
unknown (`null`) for others.

The quota **limit** is static per model/tier, so it only needs (re)learning when
the free-model landscape changes. There are **two** triggers:

- **A — a new confirmed-free model appeared** (models.dev `free`/`0-cost`, or a
  free provider) since the prior run; and
- **B — an existing model's free/0-cost status changed** in either direction
  (free→paid, paid→free, 0-cost→priced) — an old free model could have changed,
  so its quota and combo membership must be re-evaluated too.

When either trigger fires we do a **full recalc** (re-verify everyone, since one
change is a signal others may have shifted); on quiet days quota research does not
run. The live **remaining** quota (consumption) is a separate, cheap, daily
concern handled by `quota-sync` and is unchanged here.

## What Changes

- Gate quota research on a **free-model-change trigger** (A new free model, or B
  a changed free/0-cost status), restricted to models reachable via an existing
  OmniRoute connection. No change ⇒ quota research is skipped (idempotent), and
  the live quota/probe/health daily safety path still runs.
- On trigger, run a **full recalc**: re-search **all** endpoints (overriding the
  not-stale skip for that run) so every rule is re-verified. OmniRoute's
  `quotaTotal` is consumed as a known-limit input/cross-check; search still
  establishes hard-stop behaviour for each endpoint.
- The trigger run continues through scoring → allocation → diff → apply so that:
  - a model that **gained** free status is added as a member of any existing combo
    whose band/capability it fits (no combo is created); and
  - a model that **lost** free status is dropped from combos on rebalance (it no
    longer passes the confirmed-free gates) and its quota rule is deactivated.

## Impact

- Modified specs: `quota-research` (two triggers + full-recalc override of the
  no-daily-research rule, OmniRoute-first), `pipeline-orchestration`
  (quota-research is triggered/skipped; the trigger run adds gained-free and drops
  lost-free models on rebalance).
- Affected code: `src/fmo/composition_stages.py` (`_quota_research_stage` trigger
  + endpoint selection), free/0-cost change detection against the prior
  free-registry / catalog snapshot (both directions), `src/fmo/quota_manager.py`
  (OmniRoute-known vs search-needed; rule deactivation for lost-free).
- Depends on: `update-combo-applier-to-rebalance-only`,
  `add-forecast-driven-quality-band`.
- Pairs with: `register-new-free-models-in-omniroute`.
