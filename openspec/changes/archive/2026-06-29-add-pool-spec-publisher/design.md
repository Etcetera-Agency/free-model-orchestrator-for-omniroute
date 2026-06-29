# Design — FMO pool-spec publisher (additive)

## Publisher pipeline (reuse PipelineRunner)

```pseudo
stages = build_publisher_stages()    # [hermes-inventory, role-lifecycle, demand-forecast,
                                      #  compose, publish, usage-feedback]
def run(trigger):
  inv    = hermes_inventory()                                  # reuse (Consumer/Inventory)
  roles  = reconcile_roles(inv.roles, desired=inv.desired,
                           now=utcnow(), grace_period=GRACE)   # reuse role_lifecycle
  demand = forecast(inv)                                       # reuse forecast.*, see below
  gen    = compose(roles, demand, inv.role_pool_map)
  publish(gen)
  feedback = client.get("/api/fmo/usage")                      # recalibrate next cycle
```

## Demand (reuse, drop capacity-derived band)

```pseudo
def forecast(inv):
  raw = aggregate_demand(inv.agent_runs, inv.bindings, inv.dependencies)   # reuse
  out = {}
  for role, value in raw:
    p = protected_demand(expected=value, p95=inv.p95[role], peak_multiplier=PEAK)  # reuse
    p = apply_historical_reserve(p, multiplier=RESERVE, already_applied=...).reserved
    if value == 0:
      p = cold_start_demand(schedule=inv.sched[role], bootstrap=None,
                            role_minimum=ROLE_MIN, global_minimum=GLOBAL_MIN).value
    out[role] = p
  return out
# quality_band_for_demand REMOVED — band is intent from role policy (compose()).
```

## Compose contract

```pseudo
def compose(roles, demand, role_pool_map):
  pools = []
  for role in roles where role.status in {active, bootstrap_pending}:
    pools.append({
      "pool_id": role_pool_map[role.id],
      "combo_id": role.combo_id,                  # operator-created; FMO never creates it
      "demand": { "requests_per_day": demand[role.id],
                  "consumers": role.consumer_count,
                  "workload_class": role.workload_class },     # qualitative
      "constraints": { "free_only": role.free_only,
                       "capabilities": role.capabilities,
                       "min_context_tokens": role.min_context,  # required
                       "quality_band": { "source": "model_intelligence", "metric": "score",
                                         "category": role.quality_category,
                                         "min": role.quality_min, "max": role.quality_max,
                                         "relax": {"when":"underfilled","max_delta":role.quality_relax} } },
      "tail": {"strategy":"auto","mode":"fallback","compatibility":"strict"},
    })
  assert all(p.constraints.min_context_tokens is not None for p in pools)   # fail closed
  return {"contract_version":"fmo-pools/v1","generation":utcnow_iso(),"pools":pools}
```

## Publish (reuse OmniRouteClient + version gate)

```pseudo
def publish(gen):
  if not version_gate.evaluate(server_contract_version()).can_apply:        # gate CONTRACT
    raise ContractVersionUnsupported
  canonical_payload = canonicalize(gen)
  key = stable_hash(canonical_payload)
  resp = client.put("/api/fmo/pools", gen, idempotency_key=key)            # reuse client
  audit_change(kind="publish", generation=gen.generation, status=resp.status)
  store_published_generation(gen, key, status=resp.status)
```
