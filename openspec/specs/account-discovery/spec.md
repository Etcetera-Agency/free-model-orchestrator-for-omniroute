# account-discovery Specification

## Purpose
TBD - created by archiving change add-discovery. Update Purpose after archive.
## Requirements
### Requirement: Connections are not capacity

The system SHALL count active credential connections separately from independent
quota pools. Provider capacity SHALL be the sum of usable capacity of independent
quota pools, never the connection count times per-account quota.

#### Scenario: Shared upstream account
- GIVEN 3 OmniRoute connections backed by 1 upstream account
- WHEN capacity is computed
- THEN capacity equals one pool's quota, not three

#### Scenario: Independent accounts
- GIVEN 3 connections proven to be independent accounts
- WHEN capacity is computed
- THEN capacity is the sum of the three pools

### Requirement: Quota pool grouping order

The system SHALL assign a connection to a quota pool in order: manual override;
explicit upstream account id; rate-limit account id; identical credential
fingerprint; identical usage/reset bucket; provider adapter; conservative
fallback that groups connections as shared. Fingerprints SHALL use only non-secret
attributes.

#### Scenario: Unproven independence
- GIVEN a new connection whose independence cannot be proven
- WHEN grouping runs
- THEN it joins an existing shared pool

### Requirement: Independence status drives capacity

The system SHALL record an independence status from the canonical set and add
capacity only for `confirmed` independent pools; `inferred`, `assumed_shared` and
`unknown` SHALL NOT add guaranteed capacity. A pool merge SHALL trigger an
immediate allocation recalculation.

#### Scenario: Pool merged
- GIVEN two pools previously counted as independent are merged
- WHEN the merge is detected
- THEN allocation is recalculated because capacity may have been overstated

### Requirement: Connection-source errors are conservative

If `/api/providers` is unavailable the system SHALL forbid allocation/apply; if
`/api/rate-limits` is unavailable it SHALL reuse the last confirmed grouping;
conflicting data SHALL resolve to `unknown`.

#### Scenario: Rate-limit API down
- GIVEN `/api/rate-limits` is unavailable
- WHEN account discovery runs
- THEN the last confirmed grouping is reused rather than inventing new capacity

