# allocator Specification

## Purpose
TBD - created by archiving change add-allocation. Update Purpose after archive.
## Requirements
### Requirement: Global allocation before combos

The system SHALL allocate the usable capacity of all quota pools across all roles
globally before building any combo, so the same endpoint/account cannot be
counted as guaranteed capacity for several roles at once. Allocation SHALL reserve
pool capacity for every endpoint that becomes a member of a role's combo — the
primary AND every fallback scored member — not only the primary, so an emitted
combo never promises capacity its pools lack. A would-be combo member whose pool
has no remaining capacity after prior reservations SHALL be dropped from the
combo rather than emitted.

#### Scenario: Shared endpoint across roles
- GIVEN one endpoint eligible for three roles
- WHEN allocation runs
- THEN its quota is not promised in full to all three roles simultaneously
- AND a score row for one role is not reused as eligibility for another role

#### Scenario: Fallback members reserve their pool capacity
- GIVEN a role whose combo would include a primary and a fallback from the same
  pool
- WHEN allocation runs
- THEN both members reserve capacity against that pool
- AND the pool usage reflects the primary and the fallback, not just the primary

#### Scenario: Combo member without pool capacity is dropped
- GIVEN a candidate fallback endpoint whose pool capacity is already fully
  reserved
- WHEN the priority combo is built
- THEN that candidate is dropped from the combo
- AND the combo does not promise capacity the pool lacks

### Requirement: Hard constraints and heavy-role separation

The system SHALL keep heavy roles separated across quota pools when possible and
SHALL NOT assign a second primary for the same heavy role in the same pool.

#### Scenario: Heavy role same pool second primary
- GIVEN a heavy role already has a primary endpoint in a pool
- WHEN another endpoint from the same pool is considered as second primary
- THEN it is not selected

### Requirement: Oversubscription gate

The system SHALL reject plans where assigned demand exceeds usable free capacity.
Zero-capacity pools SHALL be treated as oversubscribed instead of causing a
division error.

#### Scenario: Zero capacity pool
- GIVEN a plan assigns demand to a pool with zero usable capacity
- WHEN the plan is validated
- THEN the plan is rejected as oversubscribed

### Requirement: One priority combo per role, no weights

The system SHALL emit exactly one combo per role or resolved grid cell as an
ordered endpoint list with `strategy = priority` (index 0 = primary, 1..N =
fallback); endpoint weights SHALL NOT be calculated or stored. Combo members
SHALL be partitioned into scored endpoints and configured router endpoints
(members of `auto_router_tail`). Scored endpoints SHALL be ordered first, by AA
quality ascending: the weakest band-eligible endpoint is the primary (position 0)
and the smartest scored endpoint is the last scored position. Configured routers
SHALL form a fallback tail appended after the last scored endpoint, never
interleaved with or placed ahead of a scored endpoint, regardless of any
score-like value. The tail SHALL be ordered by `auto_router_tail` config order. A
router SHALL be included in a role's tail only when, for that role, it passes the
access filter as free (the catalog `cost` is not trusted), covers the role's
required input modalities per its config-declared `input`, meets the role's
context-window minimum via the existing `effective_context_window` hard filter,
and passes probe/quota/breaker; a router failing any of these is skipped for that
role. Scored endpoints SHALL be bounded by the scored-slot `per_pool_cap`;
routers SHALL NOT consume that cap and SHALL be bounded by the `auto_router_tail`
length.

Every persisted allocation target SHALL carry structured combo member identity:
endpoint id, OmniRoute provider/model step, optional connection id,
provider-account id, quota-pool id, canonical-model id, canonical slug/family,
and score/audit grouping metadata. The allocator SHALL avoid adding a second
scored member with the same canonical model when another eligible candidate in
the same profile/cell can satisfy capacity and hard filters. Canonical family
concentration SHALL be reported in the constraint report. Quota-pool capacity
SHALL remain the hard blocker and SHALL NOT be relaxed for diversity.

#### Scenario: Combo output
- GIVEN an allocated role
- WHEN its combo is emitted
- THEN it is an ordered priority list with no weights
- AND the same endpoint id appears at most once in that role's combo

#### Scenario: Combo orders weakest-eligible first
- GIVEN three band-eligible scored endpoints with AA metrics low < mid < high
- WHEN the priority combo is built
- THEN position 0 is the low endpoint and the high endpoint is the last scored
  position
- AND two equal-quality endpoints are ordered by latency/reliability

#### Scenario: Configured routers pinned to the tail in config order
- GIVEN one scored endpoint and a role for which `mimocode/mimo-auto` and
  `kilo-auto/free` both qualify, with that config order
- WHEN the priority combo is built
- THEN the scored endpoint occupies position 0
- AND `mimocode/mimo-auto` then `kilo-auto/free` follow as the final fallback
  positions
- AND the routers do not consume the scored-slot `per_pool_cap`

#### Scenario: Router skipped when its effective context is below the role minimum
- GIVEN a role whose context-window minimum is 400000
- AND router `openrouter/free` whose `effective_context_window` is 200000
- AND router `mimocode/mimo-auto` whose `effective_context_window` is 1000000
- WHEN the role's tail is built
- THEN `openrouter/free` is skipped by the existing context-window hard filter
- AND `mimocode/mimo-auto` is still appended

#### Scenario: Router skipped when its declared modalities miss a role capability
- GIVEN a role requiring `image` input
- AND `auto_router_tail` entry `kilo-auto/free` declares `input = ["text"]`
- AND entry `openrouter/free` declares `input = ["text", "image"]`
- WHEN the role's tail is built
- THEN `kilo-auto/free` is skipped
- AND `openrouter/free` is still eligible if all other hard filters pass

#### Scenario: Router never outranks a scored endpoint
- GIVEN a router whose computed score value would otherwise sort ahead of a
  scored endpoint
- WHEN the priority combo is built
- THEN the router is still placed after every scored endpoint

#### Scenario: Allocation target carries structured member identity
- **WHEN** allocation persists a combo target
- **THEN** the target includes endpoint id, structured OmniRoute model step,
  provider account, quota pool, canonical model, canonical family, and score

#### Scenario: Duplicate canonical model avoided when alternative exists
- **GIVEN** two eligible endpoints map to the same canonical model
- **AND** another eligible endpoint in the same cell/profile maps to a different
  canonical model
- **WHEN** the priority combo is built
- **THEN** the combo prefers the different canonical model before duplicating the
  same canonical model

#### Scenario: Family concentration reported
- **GIVEN** accepted combo members are concentrated in one canonical family
- **WHEN** allocation persists the plan
- **THEN** the constraint report includes a canonical-family concentration
  diagnostic

#### Scenario: Quota pool remains hard gate
- **GIVEN** the more diverse candidate would oversubscribe its quota pool
- **WHEN** the priority combo is built
- **THEN** that candidate is rejected despite improving canonical diversity

### Requirement: Degraded modes, no paid fallback

If no free endpoint has enough capacity for a role, the system SHALL omit that
role from the plan rather than allocate paid or unsafe fallback capacity. When the
only eligible free endpoints for a role are configured routers, the system SHALL
emit a combo consisting solely of those routers as the fallback tail; this remains
a free-tier plan and SHALL NOT be treated as paid fallback.

#### Scenario: No endpoint with capacity
- GIVEN a role's demand exceeds every matching free endpoint capacity
- WHEN allocation runs
- THEN the role is absent from the plan

#### Scenario: Router-only combo is allowed
- GIVEN a role whose only eligible free endpoints are configured routers
- WHEN its combo is built
- THEN the combo contains those routers as its fallback tail in config order
- AND no paid or unsafe fallback is introduced

### Requirement: Stability

The system SHALL keep stable allocation order when scores drift trivially and
SHALL tolerate endpoints missing from the current score map.

#### Scenario: Missing score during stable order
- GIVEN a previous endpoint is not present in current scores
- WHEN stable order is computed
- THEN no `KeyError` is raised
