# quota-attribution Specification

## ADDED Requirements

### Requirement: quota_pool is optional

The system SHALL operate through a `quota_attribution_group` and SHALL NOT require
OmniRoute to supply a `quota_pool`. When the pool is unknown, usage is still
tracked at endpoint/provider level but is not distributed to confirmed
independent pools.

#### Scenario: No OmniRoute pool
- GIVEN an endpoint whose OmniRoute `quota_pool` is unknown
- WHEN usage is attributed
- THEN it is recorded against a `quota_attribution_group`, not dropped

### Requirement: Capacity by attribution status

The system SHALL grant capacity by status: `confirmed` independent → full;
`inferred` → discounted/opportunistic only; `assumed_shared` → one conservative
shared capacity; `unknown` → zero guaranteed capacity. Multiple accounts SHALL
NOT multiply capacity until independence is confirmed.

#### Scenario: Two accounts, independence unknown
- GIVEN two accounts of one provider with status `unknown`
- WHEN capacity is computed
- THEN they add no guaranteed capacity

### Requirement: Merge and split with audit

The system SHALL merge groups when evidence shows shared counters and split them
when independence is confirmed, recalculating forecast and allocation each time
and storing evidence for every decision.

#### Scenario: Confirmed independence
- GIVEN two accounts later proven to have independent counters
- WHEN the split is applied
- THEN new confirmed capacity is added and allocation is recalculated

### Requirement: No-auth scopes are not account capacity

The system SHALL model no-auth scopes (global, IP, installation, device, session,
unknown) without treating IP/installation scope as account capacity; an unknown
scope SHALL be opportunistic only.

#### Scenario: IP-scoped no-auth provider
- GIVEN a keyless provider whose quota is IP-scoped
- WHEN capacity is computed
- THEN it is not modeled as per-account capacity
