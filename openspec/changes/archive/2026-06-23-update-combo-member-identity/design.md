# Design: structured combo member identity

## Context

OmniRoute combo model steps support `providerId` and `connectionId`. FMO's apply
path currently reduces allocation targets to endpoint id strings before `PUT
/api/combos/{id}`, so it cannot intentionally pin a combo member to a provider
connection/account. Separately, FMO already maps endpoints to canonical models
for AA scoring and profile normalization, but combo construction does not use
canonical identity as a diversity boundary.

## Goals

- Carry the full identity of every combo member from scoring/allocation through
  diff snapshots and apply.
- Render OmniRoute structured combo steps when enough provider/account data is
  known.
- Keep endpoint id as the deterministic internal join key.
- Expose grouping facts required by future reviewer/rebalance: quota pool,
  provider, account, canonical model, canonical family.

## Non-Goals

- No LLM reviewer changes in this slice.
- No grid topology changes or cell splitting.
- No new live OmniRoute API shape beyond the existing structured combo step
  format.
- No backward compatibility layer for old snapshot shapes unless needed for
  tests in this repository.

## Member Shape

Allocation targets SHALL use this stable shape:

```json
{
  "endpoint_id": "uuid-or-endpoint-key",
  "priority": 1,
  "combo_step": {
    "kind": "model",
    "model": "provider/model",
    "providerId": "provider",
    "connectionId": "connection-or-null",
    "weight": 0
  },
  "groups": {
    "provider_id": "provider",
    "provider_account_id": "uuid",
    "quota_pool_id": "uuid",
    "canonical_model_id": "uuid",
    "canonical_slug": "gemini-2.5-flash",
    "canonical_family": "gemini-flash"
  },
  "score": 0.91
}
```

`combo_step.connectionId` is included only when FMO has a concrete
`provider_accounts.omniroute_connection_id`. If connection id is absent, the step
still pins `providerId` and `model`.

## Pseudocode

```python
def _allocation_stage(...):
    score_rows = SELECT role score + endpoint identity + account + provider +
                 quota_pool + canonical slug/family
    endpoints = [candidate_from_row(row) for row in score_rows]

    plan = allocate_globally(roles, endpoints, demand)
    combo = build_priority_combo(..., endpoints=endpoints)

    targets = [
        build_allocation_target(endpoint, priority=index + 1)
        for index, endpoint in enumerate(combo.endpoints)
    ]

    allocation_plans.upsert(..., targets=targets)
```

```python
def build_priority_combo(...):
    used_pools = set()
    used_canonical_models = set()
    concentration = []

    for endpoint in score_order:
        if pool_capacity_would_exceed(endpoint):
            continue
        if canonical_model_seen(endpoint) and has_safe_unseen_alternative:
            concentration.append({"endpoint_id": endpoint["id"], "reason": "duplicate_canonical_model"})
            continue
        accept(endpoint)

    return Combo(..., endpoints=accepted_endpoint_ids, diagnostics=concentration)
```

```python
def _diff_stage(...):
    desired_steps = [target["combo_step"] for target in plan["targets"]]
    desired_keys = [target["endpoint_id"] for target in plan["targets"]]
    before_steps = normalize_live_combo_steps(current[combo_id])

    diff = {
        "combo_id": combo_id,
        "before": before_steps,
        "after": desired_steps,
        "before_endpoint_ids": ...,
        "after_endpoint_ids": desired_keys,
        "add": ...,
        "remove": ...,
    }
```

```python
def _apply_stage(...):
    desired = diff["state_json"]["after"]
    client.put(f"/api/combos/{combo_id}", {"models": desired}, ...)
```

## Validation Rules

- Every target must have `endpoint_id`, `priority`, `combo_step.kind == "model"`,
  non-empty `combo_step.model`, and non-empty `combo_step.providerId`.
- `combo_step.connectionId`, when present, must match the endpoint's provider
  account connection id.
- Two accepted scored members SHOULD NOT share the same `canonical_model_id` when
  an eligible alternative in the same cell/profile exists.
- Canonical family concentration is recorded in `constraint_report`, even when
  not rejected.
- Quota pool capacity remains the hard blocker; family diversity is a selection
  guard/reporting signal, not an excuse to exceed quota.

## Migration Plan

This is not a database migration. `allocation_plans.targets` and
`combo_snapshots.state_json` are JSONB and can hold the richer target shape. Tests
SHALL update fixtures to seed structured targets. Old unstructured snapshots may
be ignored by the new apply path because the normal pipeline writes fresh diff
snapshots before apply.

## Dependency

`update-smart-combo-review-context` should be implemented after this slice so the
reviewer can receive and propose patches against the same identity and grouping
model deterministic code validates.
