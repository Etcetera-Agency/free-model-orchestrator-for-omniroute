## ADDED Requirements

### Requirement: Live API bridge forwards management combo routes

The shared OmniRoute client and live API bridge SHALL allow FMO to reach the
management combo routes required for apply through the configured OmniRoute base
URL. `GET /api/combos`, `GET /api/combos/{id}`, and the existing-combo write
route under `/api/combos/{id}` SHALL be forwarded to OmniRoute with management
auth headers intact. The bridge SHALL NOT return a bridge-level `404` for those
allowed paths, and SHALL NOT synthesize combo payloads.

#### Scenario: Bridge exposes management combo routes
- GIVEN the shared OmniRoute client is configured with the live API bridge base
  URL
- AND valid management auth is available
- WHEN FMO requests `GET /api/combos`
- THEN the request reaches OmniRoute's management combo handler
- AND the response is not a bridge-level `404`

#### Scenario: Bridge preserves management auth failures
- GIVEN the shared OmniRoute client is configured with the live API bridge base
  URL
- AND management auth is missing or invalid
- WHEN FMO requests an allowed `/api/combos*` management path
- THEN the request reaches OmniRoute's management auth layer
- AND the failure is reported as an auth failure rather than a bridge-level
  `404`

### Requirement: Combo test helper remains unavailable

The bridge and shared OmniRoute client SHALL keep `/api/combos/test` unavailable
to FMO. Combo health checks SHALL continue to use the OpenAI-compatible combo
model path, not OmniRoute's management combo-test helper.

#### Scenario: Bridge denies combo test helper
- GIVEN the shared OmniRoute client is configured with the live API bridge base
  URL
- WHEN FMO attempts to call `/api/combos/test`
- THEN the request is rejected by FMO or bridge policy
- AND it is not used as the apply smoke-test path
