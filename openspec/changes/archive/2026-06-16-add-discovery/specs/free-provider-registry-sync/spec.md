# free-provider-registry-sync Specification

## ADDED Requirements

### Requirement: Free registry as no-auth/free source

The system SHALL build the built-in no-auth and free-tier catalog from
`/api/free-models` (fields: provider, modelId, displayName, monthlyTokens,
creditTokens, freeType, poolKey, tos), not from `/api/providers`. Selection
SHALL include all no-auth providers and OAuth/API-key providers where
`hasFree = true`.

#### Scenario: No-auth provider has no connection
- GIVEN a built-in no-auth provider with no credential connection
- WHEN the registry sync runs
- THEN it is represented as a virtual provider instance, not treated as missing

### Requirement: poolKey deduplication

The system SHALL count a shared `poolKey` only once, using the maximum budget
within that pool, then additionally scope it by account/IP/session only when the
upstream quota semantics require it.

#### Scenario: Shared pool across models
- GIVEN several models sharing one `poolKey`
- WHEN capacity is summed
- THEN the pool is counted once at its maximum budget

### Requirement: Rankings are scoring, not discovery

The system SHALL use Free Provider Rankings only as a quality signal; providers
without scored models SHALL NOT be discovered from rankings.

#### Scenario: Unscored provider
- GIVEN a provider absent from rankings
- WHEN discovery runs
- THEN it is still discovered via the free-models catalog, not omitted

### Requirement: Web-cookie excluded from auto discovery

The system SHALL exclude web-cookie providers from automatic model discovery and
the daily model refresh, even if they report `hasFree`.

#### Scenario: Web-cookie provider in registry
- GIVEN a web-cookie provider with `hasFree`
- WHEN the daily model refresh runs
- THEN its models are not auto-discovered or refreshed
