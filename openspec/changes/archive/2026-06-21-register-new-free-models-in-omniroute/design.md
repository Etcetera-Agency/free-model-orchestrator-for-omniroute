# Design — register new free models in OmniRoute

## OmniRoute API (verified)

`POST /api/provider-models` (`../OmniRoute/src/app/api/provider-models/route.ts`):

```
body: { provider, modelId, modelName?, source?, apiFormat?, supportedEndpoints?, targetFormat? }
-> addCustomModel(provider, modelId, modelName, source||"manual", apiFormat,
                  supportedEndpoints, targetFormat)
auth: required (isAuthenticated)
```

So a single authenticated POST adds a model under an existing provider. There is
no provider/connection creation here — `provider` must already exist. (`PUT`,
`PATCH`, `DELETE` also exist; we use only POST, additively.)

`GET /api/rate-limits` gives our connections (`{connectionId, provider,
enabled}`), i.e. which providers we can register under.

## Registration step (pseudocode)

```python
def register_new_free_models(deps, newly_free_models):
    our_providers = {c["provider"] for c in get_rate_limits(client)["connections"] if c["enabled"]}
    existing = existing_endpoint_keys(transaction)            # {(provider, modelId)} already known

    for m in newly_free_models:                               # confirmed free/0-cost only
        if m.provider not in our_providers:
            report("unreachable_new_free_model", m)           # operator adds connection; no recalc
            continue
        if (m.provider, m.model_id) in existing:
            continue                                          # idempotent: already registered
        client.post("/api/provider-models",
                    {"provider": m.provider, "modelId": m.model_id,
                     "modelName": m.display_name, "source": "fmo",
                     "apiFormat": m.api_format, "supportedEndpoints": m.endpoints},
                    idempotency_key=hash(m.provider, m.model_id))
        registered.append(m)
    return registered
```

Guarantees:
- **Free-only**: `newly_free_models` is sourced from models.dev `free`/`0-cost`
  and free-provider registry; a paid model is never passed in.
- **Idempotent**: skip if `(provider, modelId)` is already an endpoint; the POST
  also carries an idempotency key.
- **Additive**: only POST; no DELETE/PATCH of existing provider-models.
- **Reachable-only**: `provider in our_providers`; otherwise report and skip.

## Ordering

Registration runs at the start of a triggered run (before catalog scan / quota
research) so the new endpoint exists for matching → quota research → scoring →
allocation → apply, landing it in a fitting existing combo on rebalance.
Registration never makes a model routable on its own — it must still pass
capability/quota/probe/band gates.

## Boundary

This is the only OmniRoute write outside `fmo-` combo mutation. It is constrained
to additive, idempotent, confirmed-free registration; it never edits paid models,
never deletes, and never creates providers/connections (credentials stay with the
operator).
