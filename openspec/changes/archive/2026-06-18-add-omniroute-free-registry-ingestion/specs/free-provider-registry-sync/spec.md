## ADDED Requirements

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
