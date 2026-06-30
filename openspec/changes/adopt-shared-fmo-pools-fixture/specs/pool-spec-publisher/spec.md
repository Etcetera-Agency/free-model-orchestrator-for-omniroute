# pool-spec-publisher Specification

## MODIFIED Requirements

### Requirement: Wire-contract conformance

The system SHALL emit a published generation that conforms exactly to the canonical
`fmo-pools/v1` contract the OmniRoute ingester accepts, and SHALL be locked to that
shape by a single shared golden fixture that is byte-identical to the OmniRoute copy and
serves as the only contract source of truth. The emitted payload SHALL use the
`contract_version` literal `fmo-pools/v1`; a `demand` object whose `requests_per_day` is
an integer request count and whose FMO-owned `consumers` is an integer count, alongside
`workload_class`; a `constraints` object with `free_only`, `capabilities`, an integer
`min_context_tokens`, and a `quality_band` intent whose `relax` is `{ max_delta, when }`;
and a `tail` intent object (`strategy`, `mode`, `compatibility`) carrying no explicit
members. The system SHALL draw `capabilities` tokens from the shared capability
vocabulary OmniRoute matches against, and SHALL set `quality_band.category` to a category
name OmniRoute's model-intelligence resolver recognizes. Generation publish SHALL remain
idempotent by payload hash (`Idempotency-Key` = payload hash) and SHALL NOT key
idempotency on the generation string.

#### Scenario: Emitted payload matches the shared fixture

- GIVEN a composed generation from a Hermes inventory
- WHEN the payload is built
- THEN it conforms to the single shared `fmo-pools/v1` fixture used by both repos
- AND `demand.requests_per_day` is an integer and `demand.consumers` is an integer count

#### Scenario: Shared fixture is byte-identical across repos

- GIVEN the FMO copy and the OmniRoute copy of the canonical fixture
- WHEN they are compared
- THEN they are byte-identical
- AND the conformance test loads that shared fixture, not a private one

#### Scenario: Idempotency stays payload-hash based

- GIVEN a composed generation
- WHEN it is published
- THEN the `Idempotency-Key` is the payload hash
- AND it is not the generation string
