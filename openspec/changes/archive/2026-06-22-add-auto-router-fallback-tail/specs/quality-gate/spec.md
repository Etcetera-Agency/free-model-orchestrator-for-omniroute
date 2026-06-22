# quality-gate Specification Delta

## MODIFIED Requirements

### Requirement: Unverifiable gate handling

If the gate metric is missing for an endpoint the system SHALL set
`quality_gate_status = unverifiable` and exclude the endpoint from the role
unless `allow_unverified_quality_gate` is set. This exclusion SHALL NOT apply to
configured router endpoints (members of `auto_router_tail`): a router has no
stable underlying model, so the role quality band is inapplicable to it. A router
SHALL be exempt from the band/quality-gate filter entirely — it is neither
excluded as `unverifiable` nor ordered as a band-eligible scored member — and
SHALL remain eligible only as the combo's fallback tail.

#### Scenario: Missing gate metric
- GIVEN a role gate on `coding_index` and a non-router endpoint with no coding
  index
- WHEN the gate is evaluated and override is off
- THEN the endpoint is excluded as unverifiable

#### Scenario: Router is exempt from the band
- GIVEN a role with a quality band and a configured router endpoint that has no AA
  quality metric
- WHEN the gate is evaluated and `allow_unverified_quality_gate` is off
- THEN the router is not excluded as unverifiable
- AND it is not ordered as a band-eligible scored member
- AND it remains eligible for the combo's fallback tail
