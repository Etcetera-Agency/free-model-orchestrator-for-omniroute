# register-new-free-models-in-omniroute

## Why

When a brand-new confirmed-free model (models.dev `free`/`0-cost`, or a
free-provider model) appears, it can only be probed, scored and added to a combo
if OmniRoute knows it as a usable endpoint. If the model is reachable through one
of our existing connections but is not yet a registered provider-model, the
orchestrator must register it in OmniRoute.

OmniRoute supports this: `POST /api/provider-models`
(`../OmniRoute/src/app/api/provider-models/route.ts`) calls
`addCustomModel(provider, modelId, modelName, source, apiFormat,
supportedEndpoints, targetFormat)` under an authenticated request — i.e. it adds
a model under an **existing** provider/connection.

The orchestrator does not manage credentials, so it registers a model only under
a connection that already exists. A new free model whose provider has no
connection is out of scope: per the operator's decision it does not trigger a
recalc and is not registered (the operator adds the connection first).

This extends the orchestrator's OmniRoute write surface beyond `fmo-` combos for
the first time, so the boundary is stated explicitly and kept narrow: additive,
idempotent, confirmed-free only, never deletes, and registration alone never
makes a model routable (it still passes quota/probe/band gates before combo
membership).

## What Changes

- When new-free-model detection (see `trigger-quota-recalc-on-free-model-changes`)
  finds a confirmed-free model reachable via an existing connection that is not
  yet a registered endpoint, register it via `POST /api/provider-models` with its
  `provider` + `modelId` (and known `apiFormat`/`supportedEndpoints`).
- Registration is **idempotent**: a model already present as an endpoint is not
  re-registered.
- Registration is **additive and free-only**: the orchestrator never registers a
  paid model and never deletes provider-models it did not need.
- Models **outside** our connections are neither registered nor recalc-triggering.
- Registration precedes catalog scan / quota research for the new model so it can
  flow into the registry and into a fitting existing combo on rebalance.

## Impact

- New capability spec: `model-registration`.
- Modified specs: `system-architecture` (the OmniRoute write surface now includes
  additive registration of confirmed-free provider-models, alongside `fmo-`
  combo mutation).
- Affected code: new `src/fmo/model_registration.py` (or a discovery-stage step)
  issuing `POST /api/provider-models`; `src/fmo/omniroute.py` already provides the
  authenticated POST.
- Depends on: `trigger-quota-recalc-on-free-model-changes` (new-free-model detection
  + reachability), `update-combo-applier-to-rebalance-only` (no combo creation).
