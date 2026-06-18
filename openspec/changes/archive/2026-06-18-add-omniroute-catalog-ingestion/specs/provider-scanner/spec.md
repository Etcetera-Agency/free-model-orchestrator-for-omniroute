## ADDED Requirements

### Requirement: Live OmniRoute catalog fetch

The system SHALL fetch the provider accounts (`GET /api/providers`) and the model
catalog (`GET /api/v1/providers/{provider}/models` per provider, or
`GET /v1/models`) from OmniRoute before each daily catalog scan, unless a catalog
payload is explicitly injected by tests or offline tooling. The fetch SHALL use the
configured OmniRoute base URL and credentials, apply bounded retries on transient
failures, and raise a structured error on auth failure, non-2xx status, or
invalid payload. A failed fetch SHALL record a failed snapshot and SHALL NOT
fabricate or overwrite the previous catalog.

#### Scenario: Catalog fetched before scan
- GIVEN no catalog payload is injected and OmniRoute credentials are configured
- WHEN the daily catalog scan starts
- THEN the provider/model catalog is fetched from the OmniRoute management API
- AND the parsed catalog is passed to the scan

#### Scenario: Fetch failure does not overwrite
- GIVEN the OmniRoute catalog fetch fails with a non-2xx status
- WHEN the scan runs
- THEN a failed snapshot is recorded
- AND the previous catalog is left unchanged
