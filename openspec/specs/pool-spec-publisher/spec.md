# pool-spec-publisher Specification

## Purpose
TBD - created by archiving change add-pool-spec-publisher. Update Purpose after archive.
## Requirements
### Requirement: Publish a pool-spec generation

The system SHALL compose Hermes roles, aggregated demand, and per-pool constraints
into one `fmo-pools/v1` generation and publish it to OmniRoute via
`PUT /api/fmo/pools`. The system SHALL NOT create, modify, or delete combos; it
SHALL reference existing OmniRoute `combo_id`s only. The system SHALL publish one
generation as one payload and SHALL NOT stream pools individually.

#### Scenario: Compose and publish from inventory
- GIVEN a Hermes inventory with active roles mapped to existing OmniRoute combos
- WHEN the publisher pipeline runs
- THEN one `fmo-pools/v1` payload is composed with one pool per active role
- AND it is sent in a single `PUT /api/fmo/pools` request

#### Scenario: Never writes combos
- GIVEN a published generation
- WHEN the publisher runs
- THEN no combo create/update/delete request is issued by FMO
- AND each pool references an existing `combo_id`

### Requirement: Publisher fills only FMO-owned fields

The system SHALL fill only the contract fields it owns: `pool_id`, `combo_id`,
`demand` (`requests_per_day`, `consumers`, `workload_class`), and `constraints`
(`free_only`, `capabilities`, `min_context_tokens`, `quality_band` intent), and the
`tail` reference. The system SHALL declare `workload_class` qualitatively and SHALL
NOT compute a token count, model score, model match, live quota, or candidate
capacity.

#### Scenario: Demand from forecast, consumers from inventory
- GIVEN aggregated demand for a role and its distinct consumer count
- WHEN the pool is composed
- THEN `demand.requests_per_day` comes from the demand forecast
- AND `demand.consumers` comes from the Hermes inventory

#### Scenario: No capacity computation
- WHEN a pool is composed
- THEN the publisher does not read candidate capacity, live quota, or model scores

### Requirement: Required per-pool context lower bound

The system SHALL require a per-pool `min_context_tokens` and SHALL fail the
generation closed (no publish) when any pool omits it. The system SHALL NOT
substitute a default context lower bound.

#### Scenario: Missing context bound fails closed
- GIVEN a role whose policy omits `min_context_tokens`
- WHEN the generation is composed
- THEN composition fails before any publish
- AND no default context lower bound is substituted

### Requirement: Idempotent generation publish

The system SHALL set the publish `Idempotency-Key` to a stable hash of the
canonical payload and SHALL record each published generation with its hash and
acknowledgement status. A retried publish of the same payload SHALL carry the same
key and payload. A changed payload SHALL produce a different key even if it reuses
the same generation marker.

#### Scenario: Retry is idempotent
- GIVEN a generation that was published once
- WHEN the same generation is published again
- THEN the `Idempotency-Key` and payload hash are identical
- AND the published-generations record reflects the acknowledgement

#### Scenario: Changed payload gets new idempotency key
- GIVEN two payloads with the same generation marker but different pool content
- WHEN both payloads are published
- THEN their `Idempotency-Key` values differ
- AND the second payload is not collapsed into the first publish attempt

### Requirement: Usage feedback recalibration

The system SHALL read per-pool usage from OmniRoute (`GET /api/fmo/usage`) and feed
it into the next cycle's demand inputs. The system SHALL NOT use usage feedback to
compute capacity or write combos.

#### Scenario: Feedback adjusts next demand
- GIVEN a prior generation and observed per-pool usage from OmniRoute
- WHEN the next publisher cycle runs
- THEN the demand forecast inputs are recalibrated from that usage

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

