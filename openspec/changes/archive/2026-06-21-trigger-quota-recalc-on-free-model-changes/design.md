# Design — new-free-model trigger for quota recalc

## Verified facts

- `_quota_research_stage` (`composition_stages.py:357`) selects **all**
  `provider_endpoints WHERE canonical_model_id IS NOT NULL`, loops, and runs
  `research_quota_rule` per endpoint → one `/v1/search` + one Instructor
  extraction each. No trigger, no freshness filter.
- OmniRoute `GET /api/usage/quota` body: `{"providers":[{"provider":...,
  "connectionId":...,"quotaUsed":N,"quotaTotal":N|null,"percentRemaining":...,
  "resetAt":...}]}` — `quotaTotal` is the known limit or `null`.
- `GET /api/rate-limits` body: per-connection `{connectionId, provider, enabled,
  active, ...}` — the set of **our connections**.
- Free models are persisted (`free_model_definitions`) and the free registry /
  catalog write snapshots, so "new since last run" is a snapshot diff.
- `build_quota_query(..., today=...)` already makes the search date-aware.

## Trigger detection (pseudocode)

Two triggers, both as a snapshot diff of the free/0-cost set against the prior
run, restricted to providers we have a connection for:

```python
def detect_free_model_changes(transaction, our_connection_providers) -> FreeChanges:
    current_free = select_free_or_zero_cost_models(transaction)   # models.dev free|0-cost + free-provider
    prior_free   = select_previous_run_free_models(transaction)   # last snapshot
    gained = current_free - prior_free        # trigger A: newly free
    lost   = prior_free - current_free        # trigger B: free -> paid / removed
    reachable = lambda s: {m for m in s if provider_of(m) in our_connection_providers}
    return FreeChanges(gained=reachable(gained), lost=reachable(lost))

def should_run_quota_recalc(transaction, client) -> bool:
    our = {c["provider"] for c in get_rate_limits(client)["connections"] if c["enabled"]}
    ch = detect_free_model_changes(transaction, our)
    return bool(ch.gained or ch.lost)         # either direction triggers full recalc
```

## Stage flow (pseudocode)

```python
def quota_research_stage(deps, ctx):
    if not should_run_quota_recalc(transaction, deps.omniroute_client):
        return StageResult(status="success", changed=False,
                           details={"effect": "idempotent_no_change", "reason": "no_free_model_change"})

    # full recalc: re-verify ALL endpoints (override the not-stale daily skip)
    omni_quota = index_by_endpoint(get_usage_quota(client))   # quotaTotal/resetAt where known
    endpoints  = all_endpoints_with_canonical(transaction)
    for ep in endpoints:                                       # bulk -> see batching note
        snapshot = run_quota_search(client, ep)               # /v1/search, date-aware
        claim    = extract_claim(snapshot, instructor=deps.llm_runtime,
                                 omni_hint=omni_quota.get(ep.id))  # quotaTotal as cross-check
        persist_rule(ep, claim)                               # hard_stop from search even if quotaTotal known
```

Notes:
- **OmniRoute-first** means `quotaTotal` is fed in as a known-limit hint /
  cross-check; we still search to determine **hard-stop** behaviour, which
  `/api/usage/quota` does not express. (Per the operator: on a trigger we search
  all, not only the `null` ones.)
- **Skip path** keeps the daily live safety (`quota-sync` remaining, probe,
  health) running — only the LLM/search limit-research is gated.
- **Batching** (optional) applies here: extraction over the bulk endpoint set can
  be sent in buckets of K snapshots per Instructor call (`ceil(N/K)` calls), with
  per-endpoint regex fallback. Most relevant on the first run / a provider dump.

## Downstream — gained-free in, lost-free out

The trigger run is a normal `full` continuation. After quota research:

- **gained free** — the endpoint has a fresh rule and is confirmed-free, so
  `role-scoring → allocation → diff → apply` adds it as a **member** of any
  existing combo whose band/capability it fits (rebalance-only; no combo
  creation). If it fits no existing combo it stays as registered free capacity,
  unused until an operator creates a combo for that tier.
- **lost free** — re-classification no longer treats it as free (paid-charge /
  non-zero price evidence), so access-classification excludes it, its quota rule
  is deactivated, and `allocation → diff → apply` **drops it** from any combo it
  was in on rebalance. The orchestrator does not delete the provider-model
  (additive boundary); it only removes it from combos and deactivates the rule.
