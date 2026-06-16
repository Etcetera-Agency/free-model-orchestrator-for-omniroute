# quota-manager Specification

## Purpose
TBD - created by archiving change add-quota. Update Purpose after archive.
## Requirements
### Requirement: Effective remaining counter

The system SHALL compute effective remaining quota from live counters, recent
attribution and reservations. If every counter source is unknown, effective
remaining SHALL be unknown. Pending reservations and safety buffer MAY make
effective remaining negative; that result SHALL be preserved.

#### Scenario: No reliable counter
- GIVEN no reliable live, attributed or reserved counter exists
- WHEN effective remaining is computed
- THEN the result is unknown

#### Scenario: Negative effective remaining
- GIVEN pending reservations plus safety buffer exceed remaining quota
- WHEN effective remaining is computed
- THEN the negative value is returned
### Requirement: Hard-stop gating

The system SHALL require provider hard-stop semantics before treating free quota
as usable.

#### Scenario: No hard stop
- GIVEN a provider has free quota but no confirmed hard stop
- WHEN quota is evaluated for allocation
- THEN the endpoint is rejected

#### Scenario: Hard stop false
- GIVEN `require_hard_stop(False)` is called
- WHEN validation runs
- THEN it raises `ValueError`
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

