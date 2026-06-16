# quota-manager Specification

## ADDED Requirements

### Requirement: Effective remaining counter

The system SHALL compute, per metric, `effective_remaining = min(provider_reported_remaining,
limit - locally_observed_usage) - pending_reserved - safety_buffer`, using only
reliable values; if no reliable value exists the endpoint SHALL be excluded.

#### Scenario: No reliable counter
- GIVEN neither provider-reported remaining nor a reliable local counter exists
- WHEN effective remaining is computed
- THEN the endpoint is excluded

### Requirement: Hard-stop gating

The system SHALL admit an endpoint to a combo only if a hard stop after free
quota is guaranteed by the provider or OmniRoute; otherwise the endpoint SHALL
NOT be admitted at all. An endpoint already exhausted at calc time SHALL be
excluded for that batch.

#### Scenario: No hard stop
- GIVEN an endpoint whose provider cannot stop after free quota is exhausted
- WHEN combos are built
- THEN the endpoint is not admitted

### Requirement: Reservation only for own probes

The system SHALL reserve quota only for its own probes; production traffic flows
through OmniRoute and requires no per-request reservation by the orchestrator.

#### Scenario: Production request
- GIVEN production traffic uses a combo
- WHEN the orchestrator plans capacity
- THEN it does not reserve quota per production request

### Requirement: Reset handling

After a reset the system SHALL NOT blindly zero counters; it SHALL request live
quota, update counters, reclassify access, and only then allow probing.

#### Scenario: After reset
- GIVEN a quota pool just reset
- WHEN the manager processes it
- THEN it fetches live quota and reclassifies before any probe

### Requirement: Historical reserve guard

The system SHALL reject any forecast record marked as using a historical source
without the configured historical reserve (`historical_reserve_multiplier`)
applied.

#### Scenario: Missing reserve
- GIVEN a record flagged historical-source but without the reserve applied
- WHEN the manager validates it
- THEN the record is rejected
