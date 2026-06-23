# Change: Carry structured combo member identity through allocation and apply

## Why

FMO currently emits combo members as a plain ordered list of endpoint ids. That
is not enough for the default combo grid and future smart reviewer: OmniRoute
combo steps can pin a target to `provider/model` and optionally to a concrete
`connectionId`, while FMO's allocator only carries the endpoint id and quota
pool. The code also has canonical model/family data, but combo building does not
use it to avoid duplicate underlying-model concentration.

Before an LLM can propose safe rebalance patches, deterministic code must own the
member identity model: endpoint, provider/model, account/connection, quota pool,
canonical model, and canonical family. That lets the system validate and render
provider/model/account choices without relying on LLM judgment.

## What Changes

- Extend allocation targets from `{"endpoint_id", "priority"}` to a structured
  combo member identity carrying:
  - `endpoint_id`;
  - `provider_model_id`;
  - OmniRoute `provider_id`;
  - optional OmniRoute `connection_id`;
  - `provider_account_id`;
  - `quota_pool_id`;
  - `canonical_model_id`;
  - canonical slug/family when known;
  - score and grouping metadata needed for deterministic audit.
- Keep endpoint ids as the internal stable key, but render OmniRoute combo
  members as structured model steps:

  ```json
  {
    "kind": "model",
    "model": "provider/model",
    "providerId": "provider",
    "connectionId": "optional-account-connection-id",
    "weight": 0
  }
  ```

- Reuse existing canonical grouping from model matching/profile normalization:
  provider-specific endpoints for the same underlying model share canonical slug
  and canonical model id; family comes from `canonical_models.family` when known.
- Add deterministic grouping guards for combo construction:
  - quota pool capacity remains the hard capacity gate;
  - provider/account grouping is exposed to plans and snapshots;
  - canonical model duplicates are bounded within a scored combo unless no safe
    alternative exists;
  - canonical family concentration is reported for audit/reviewer context.
- Preserve existing priority strategy and deterministic apply safety:
  drift checks, idempotency, smoke, rollback, and dry-run behavior stay in force.

## Impact

- Affected specs: `allocator`, `combo-applier`, `audit-rollback`.
- Affected code: `src/fmo/allocation.py`,
  `src/fmo/composition_stages/allocation.py`,
  `src/fmo/composition_stages/apply.py`, persistence snapshots, tests.
- Enables the next slice, `update-smart-combo-review-context`, to accept or reject
  LLM patches against explicit provider/model/account and canonical grouping
  identities.
