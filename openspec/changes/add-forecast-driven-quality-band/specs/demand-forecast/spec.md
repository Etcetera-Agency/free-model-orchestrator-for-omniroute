# demand-forecast Specification

## ADDED Requirements

### Requirement: Quality band widens to cover protected demand

The system SHALL size a combo's quality band from the forecast: starting at the
seed anchor, the band widens (down to an adequacy floor, and upward without a
fixed ceiling) until the confirmed-free capacity of in-band endpoints covers the
role's `protected_requests`. The seed anchor may therefore sit anywhere within
the resulting band. When in-band confirmed-free capacity cannot cover protected
demand even at the floor, the role SHALL be marked `degraded` rather than
admitting below-floor or paid capacity.

#### Scenario: Quality band widens to cover protected demand
- GIVEN a seed anchor and a `protected_requests` larger than the anchor model's
  free capacity alone
- WHEN the band is computed
- THEN the band widens around the anchor to include enough confirmed-free in-band
  capacity to cover protected demand
- AND when even the widest in-band free capacity is insufficient the role is
  marked `degraded`, not filled with below-floor or paid endpoints
