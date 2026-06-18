# free-provider-registry-sync Specification

## Purpose
TBD - created by archiving change add-discovery. Update Purpose after archive.
## Requirements
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

### Requirement: Live free-model registry fetch

The system SHALL fetch the authoritative free-model registry (and free-provider
rankings) from the OmniRoute management API before building the free registry,
unless a registry payload is explicitly injected. The fetch SHALL use configured
credentials with bounded retries and SHALL raise a structured error on auth
failure or non-2xx status. The system SHALL validate the registry against the
expected schema, report any drift (unknown or missing fields) instead of silently
dropping it, and persist the sync outcome (model count, drift, errors).

#### Scenario: Registry fetched before build
- GIVEN no registry payload is injected and credentials are configured
- WHEN free-registry sync runs
- THEN the registry is fetched from the OmniRoute management API
- AND the parsed registry is passed to the build step

#### Scenario: Schema drift reported
- GIVEN the fetched registry contains an unexpected or missing field
- WHEN the registry is validated
- THEN the drift is reported in the sync outcome
- AND the sync does not silently drop the affected entries
