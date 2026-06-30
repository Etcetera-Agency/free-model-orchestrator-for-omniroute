# pool-spec-publisher Specification

## ADDED Requirements

### Requirement: Wire-contract conformance

The system SHALL emit a published generation that conforms exactly to the canonical
`fmo-pools/v1` contract the OmniRoute ingester accepts, and SHALL be locked to that
shape by a shared golden fixture and a deterministic conformance check. The emitted
payload SHALL use the `contract_version` literal `fmo-pools/v1`; a `demand` object with
`requests_per_day` and the FMO-owned `consumers` and `workload_class`; a `constraints`
object with `free_only`, `capabilities`, an integer `min_context_tokens`, and a
`quality_band` intent whose `relax` is `{ max_delta, when }`; and a `tail` intent object
(`strategy`, `mode`, `compatibility`) carrying no explicit members. The system SHALL draw
`capabilities` tokens from the shared capability vocabulary OmniRoute matches against,
and SHALL set `quality_band.category` to a category name OmniRoute's model-intelligence
resolver recognizes. Generation publish SHALL remain idempotent by payload hash
(`Idempotency-Key` = payload hash) and SHALL NOT key idempotency on the generation
string.

#### Scenario: Emitted payload matches the golden fixture

- GIVEN a composed generation from a Hermes inventory
- WHEN the payload is built
- THEN it validates against the shared `fmo-pools/v1` golden schema/fixture
- AND it uses `contract_version`, a `quality_band.relax` of `{ max_delta, when }`, and a
  `tail` intent object with no members

#### Scenario: Capabilities and category use the shared vocabulary

- GIVEN a pool with capability and quality constraints
- WHEN the constraints are composed
- THEN `capabilities` tokens are drawn from the shared vocabulary OmniRoute matches
- AND `quality_band.category` is a name OmniRoute's intelligence resolver recognizes

#### Scenario: Idempotency stays payload-hash based

- GIVEN a composed generation
- WHEN it is published
- THEN the `Idempotency-Key` is the payload hash
- AND it is not the generation string
