# omniroute-client Specification

## MODIFIED Requirements

### Requirement: Version handshake gates writes

The system SHALL fetch the OmniRoute version at startup and check the compatibility
matrix. The handshake SHALL gate **contract acceptance** for the pool-spec publish
(`fmo-pools/v1` via `PUT /api/fmo/pools`): when the running OmniRoute version does
not support the published contract version, the client SHALL refuse to publish and
SHALL keep read-only calls allowed. Because FMO no longer writes combos, the gate no
longer governs a combo-apply path.

#### Scenario: Unsupported contract version refuses publish
- GIVEN the running OmniRoute version does not support `fmo-pools/v1`
- WHEN the orchestrator attempts to publish a generation
- THEN the publish is refused
- AND read-only calls (including usage feedback) remain allowed

#### Scenario: Supported version publishes
- GIVEN the running OmniRoute version supports `fmo-pools/v1`
- WHEN a generation is published
- THEN the `PUT /api/fmo/pools` request is sent with the idempotency key
