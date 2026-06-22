# scheduler Specification Delta

## ADDED Requirements

### Requirement: Weekly tokens-per-request recalibration cadence

The system SHALL run a tokens-per-request recalibration job on its own weekly cron
(`tokens_per_request_recalibration_cron`, default Sundays 05:00), separate from
the daily pipeline. On a non-matching tick the job SHALL be a no-op. On a matching
tick it SHALL load accumulated calibration observations and the current global
factor, refine the factor, persist it, recompute self-derived endpoint capacities,
and persist them. The job SHALL hold a run lock so it does not overlap itself or a
daily run; when the lock is already held it SHALL be a no-op that writes nothing.

#### Scenario: Weekly recalibration fires
- GIVEN the configured weekly recalibration cron time arrives
- WHEN the scheduler ticks
- THEN the recalibration job refines the global factor and recomputes derived
  capacities

#### Scenario: Non-matching tick is a no-op
- GIVEN a timestamp that does not match the weekly recalibration cron
- WHEN the scheduler ticks
- THEN no recalibration runs and nothing is written

#### Scenario: Recalibration does not overlap a running job
- GIVEN the recalibration run lock is already held
- WHEN the weekly tick fires
- THEN the job does not run and no factor or capacity is written
