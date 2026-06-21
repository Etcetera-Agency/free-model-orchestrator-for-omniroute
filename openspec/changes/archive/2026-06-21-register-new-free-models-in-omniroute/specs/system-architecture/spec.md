# system-architecture Specification

## ADDED Requirements

### Requirement: OmniRoute write surface is combos plus additive free-model registration

The orchestrator's writes to OmniRoute SHALL be limited to two operations:
mutating `fmo-` combos, and additively registering confirmed-free provider-models
under existing connections. It SHALL NOT create providers or connections (those
require credentials owned by the operator), SHALL NOT delete provider-models, and
SHALL NOT write any paid model. All other OmniRoute interaction remains read-only.

#### Scenario: Registration is the only added write
- GIVEN the orchestrator runs against OmniRoute
- WHEN it mutates OmniRoute
- THEN it either changes an `fmo-` combo or additively registers a confirmed-free
  provider-model under an existing connection
- AND it never creates a provider/connection, deletes a provider-model, or writes
  a paid model
