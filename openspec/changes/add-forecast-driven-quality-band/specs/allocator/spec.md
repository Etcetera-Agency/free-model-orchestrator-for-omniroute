# allocator Specification

## MODIFIED Requirements

### Requirement: One priority combo per role, no weights

The system SHALL emit exactly one combo per role as an ordered endpoint list with
`strategy = priority` (index 0 = primary, 1..N = fallback); endpoint weights SHALL
NOT be calculated or stored. The priority order SHALL be by AA quality
**ascending** — the weakest band-eligible endpoint is the primary (position 0)
and the smartest is the last fallback — so OmniRoute's fallback chain escalates
from cheap/abundant free capacity to scarce high-quality free capacity only when
earlier members are exhausted or failing. Among endpoints of equal quality the
faster/more-reliable one SHALL come first. Per-pool caps and heavy-role pool
separation are unchanged.

#### Scenario: Combo output
- GIVEN an allocated role
- WHEN its combo is emitted
- THEN it is an ordered priority list with no weights

#### Scenario: Combo orders weakest-eligible first
- GIVEN three band-eligible endpoints with AA metrics low < mid < high
- WHEN the priority combo is built
- THEN position 0 is the low endpoint and the high endpoint is last
- AND two equal-quality endpoints are ordered by latency/reliability
