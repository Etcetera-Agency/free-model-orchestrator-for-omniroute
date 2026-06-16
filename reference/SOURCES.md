# Официальные источники, использованные при детализации

## OmniRoute

- https://github.com/diegosouzapw/OmniRoute
- https://github.com/diegosouzapw/OmniRoute/blob/main/docs/API_REFERENCE.md

Подтверждённые группы API:

- provider management;
- provider models;
- model catalog;
- pricing;
- rate limits;
- monitoring health;
- telemetry summary;
- usage;
- resilience;
- combos;
- evals;
- OpenAI-compatible `/v1/models` и chat completions.

## models.dev

- https://models.dev/
- https://models.dev/api.json
- https://models.dev/models.json
- https://models.dev/catalog.json

## Artificial Analysis

- https://artificialanalysis.ai/data-api/docs
- Base URL: `https://artificialanalysis.ai/api/v2`
- Language models: `/language/models`


## OmniRoute free/no-auth internals

- `docs/guides/FREE_PROVIDER_RANKINGS.md`
- `docs/getting-started/FREE-TIERS-GUIDE.md`
- `docs/reference/FREE_TIERS.md`
- `src/shared/constants/providers.ts`
- `src/lib/freeProviderRankings.ts`
- `open-sse/config/freeModelCatalog.ts`
- `open-sse/config/freeModelCatalog.data.ts`
- `open-sse/config/freeTierCatalog.ts`
- `src/app/api/free-models/route.ts`
- `src/app/api/free-tier/summary/route.ts`
- `src/app/api/providers/route.ts`

Relevant API:

```text
GET /api/free-models
GET /api/free-provider-rankings
GET /api/free-tier/summary
GET /api/providers
```


## Scope decision

`WEB_COOKIE_PROVIDERS` присутствуют в OmniRoute. Они исключены только из automatic model discovery, но могут использоваться как static/manual fallback candidates для совместимых ролей.


## Artificial Analysis scoring scope

Scoring v1 использует только:

```text
intelligence_index
coding_index
agentic_index
median_output_tokens_per_second
median_end_to_end_seconds
```

Все остальные поля сохраняются только в raw snapshot.


## Context-window policy

Context capacity is stored per provider endpoint. Canonical model metadata is only one input; provider-specific and probed limits can reduce the effective value.


## Simplified context policy

Each role has only `minimum_context_window`. No preferred context, buckets, similarity grouping, or tiered role combos are used.


## Role quality gates

A role may define at most one raw Artificial Analysis minimum:

```text
intelligence_index
coding_index
agentic_index
```

The gate is a hard eligibility filter; role weights rank only the surviving models.


## Artificial Analysis index migrations

Raw index thresholds are version-bound. New index versions require percentile-based recalibration and operational validation before production rollout.


## LLM-driven index migration policy

When the Artificial Analysis index changes, a dedicated migration-agent uses the available endpoint with the highest new intelligence index to propose new role thresholds. Deterministic validation remains mandatory.


## Migration-agent implementation

- `567-labs/instructor`
- OpenAI Python SDK
- Pydantic

Instructor is used only as a structured-output and validation layer over OmniRoute. No full agent framework is required.


## Demand forecasting

Quota planning uses agent schedules, agent-to-role call profiles, observed token usage, shared-role dependencies, and maintenance workloads. Forecasts are calculated for each quota pool's actual reset horizon.


## Quota attribution

Quota pool identity may come from OmniRoute, official provider APIs/documentation, open-source provider definitions, account identifiers, credential fingerprints, or observed depletion/reset behavior. Unknown or unconfirmed account independence is handled conservatively.


## Demand reserve and cold start

Historical demand forecasts receive a fixed 20% planning reserve. Deployments without representative history use exact Hermes schedules plus configurable role bootstrap profiles, with conservative fallbacks for manual and event-driven workloads.


## Smart combo review

The reviewer operates only on ordered priority combos. Endpoint weights and weighted routing are intentionally excluded to keep the control surface minimal.


## Hermes role lifecycle

Hermes role usage is inferred from declarative agent→role bindings plus cron/session/runtime observations. Runtime history alone is not authoritative because newly added roles may not yet have any sessions.


## Environment configuration

Deployment-specific Hermes paths, adapter configuration, OmniRoute URL and credentials are supplied via environment variables. `.env.example` documents the required contract.
