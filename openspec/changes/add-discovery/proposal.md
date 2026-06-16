# add-discovery

## Why

Before access can be classified, the orchestrator must discover what exists:
free candidates from models.dev, the OmniRoute free registry, the provider
catalogs, the credential accounts and their independent quota pools, and the
canonical identity of each provider model. Source modules:
`reference/docs/modules/14,02,17,18,05`, `reference/docs/architecture/06`.

## What Changes

- Add `free-candidate-discovery`: candidate rule, per-provider cost, candidate-as-lead.
- Add `provider-scanner`: catalog fetch, snapshot+diff, A/B/C prioritization,
  endpoint upsert, false-removal protection.
- Add `account-discovery`: connections vs independent quota pools, grouping
  order, independence status, capacity = sum of independent pools.
- Add `free-provider-registry-sync`: `/api/free-models` catalog, `poolKey`
  dedup, rankings as scoring source, web-cookie excluded from auto discovery.
- Add `model-matcher`: normalization, match order, forbidden auto-matches,
  confidence thresholds, provider-specific capability precedence.

## Impact

- New specs: `free-candidate-discovery`, `provider-scanner`, `account-discovery`,
  `free-provider-registry-sync`, `model-matcher`.
- Depends on: `add-foundation`.
- Feeds: quota research, access classification, scoring, allocation.
