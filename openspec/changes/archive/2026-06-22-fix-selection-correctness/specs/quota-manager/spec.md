## ADDED Requirements

### Requirement: Shared-pool remaining is counted once across an account's endpoints

The remaining capacity of an account/quota pool SHALL be counted once for the
pool, not duplicated as independent capacity onto every endpoint of that account.
When live quota is synced for an account, its endpoints SHALL share the single
pool remaining; scoring `quota_headroom` and allocation capacity SHALL be derived
from that shared pool capacity. The sum of allocations drawn from a pool SHALL NOT
exceed the pool's remaining capacity even when several endpoints of that pool are
selected.

#### Scenario: Account remaining is not duplicated per endpoint
- GIVEN one account with remaining capacity `R` and three endpoints
- WHEN live quota is synced
- THEN the three endpoints do not each report `R` as independent capacity
- AND the pool's usable capacity is `R` in total

#### Scenario: Pool capacity bounds the sum of member allocations
- GIVEN a pool with remaining capacity `R` and two selected endpoints
- WHEN allocation draws demand from both endpoints
- THEN the combined demand assigned to the pool does not exceed `R`
- AND the oversubscription gate treats the pool as a single shared budget
