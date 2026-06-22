# hermes-inventory Specification

## ADDED Requirements

### Requirement: Auxiliary model slots are consumers

The system SHALL emit a consumer for each profile's main combo and for each
profile `auxiliary.<slot>` whose route resolves to an OmniRoute combo other than
the main combo. An auxiliary slot whose `provider` is `auto` or whose `model` is
empty SHALL NOT produce a separate consumer, because it falls back to the
profile's main combo, which is already counted.

Auxiliary consumers SHALL carry `consumer_type = auxiliary`, a `consumer` key of
`"{profile}:{slot}"`, and the slot name so downstream stages can derive the
slot's capability. Auxiliary overrides configured at the gateway or per-platform
level SHALL be emitted the same way, keyed by `"gateway:{platform}:{slot}"`.

#### Scenario: Auxiliary override becomes a consumer
- GIVEN a profile whose `config.yaml` has `auxiliary.vision` pointing at an
  OmniRoute combo distinct from the main combo
- WHEN the inventory runs
- THEN an `auxiliary` consumer is recorded for that combo keyed `"{profile}:vision"`

#### Scenario: Auto auxiliary slot is not a separate consumer
- GIVEN an `auxiliary.compression` slot with `provider: auto` or empty `model`
- WHEN the inventory runs
- THEN no separate consumer is recorded for that slot
- AND its load is attributed to the profile's main combo consumer

#### Scenario: Gateway auxiliary overrides are consumers
- GIVEN a gateway config with a top-level or per-platform `auxiliary` override to
  a distinct combo
- WHEN the gateway source is parsed
- THEN an `auxiliary` consumer is recorded keyed `"gateway:{platform}:{slot}"`
