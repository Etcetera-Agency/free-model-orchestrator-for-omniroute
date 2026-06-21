# model-registration Specification

## Purpose
Register confirmed-free provider models in OmniRoute only when an existing
operator-owned connection can host them.

## Requirements

### Requirement: Register new free models under existing connections

The system SHALL register a newly detected confirmed-free model (models.dev
`free`/`0-cost` or free-provider) in OmniRoute when the model is reachable
through an existing connection and is not yet a known endpoint, by issuing
`POST /api/provider-models` with the model's `provider` and `modelId`.
Registration SHALL be idempotent (a model already present as an endpoint is not
re-registered) and additive (the system SHALL NOT delete or repurpose
provider-models it did not register). The system SHALL register only
confirmed-free models and SHALL NOT register a paid model. Registration alone
SHALL NOT make a model routable; it still passes capability, quota and probe
gates before combo membership.

#### Scenario: New free model under a connection is registered
- GIVEN a new confirmed-free model whose provider has an existing connection and
  which is not yet an endpoint
- WHEN registration runs
- THEN `POST /api/provider-models` is issued with its provider and modelId

#### Scenario: Registration is idempotent and additive
- GIVEN a free model already present as an endpoint
- WHEN registration runs
- THEN it is not re-registered
- AND no provider-model is deleted or repurposed

#### Scenario: Model outside our connections is skipped
- GIVEN a new confirmed-free model whose provider has no connection
- WHEN registration runs
- THEN the model is reported as unreachable and not registered
- AND no provider/connection is created
