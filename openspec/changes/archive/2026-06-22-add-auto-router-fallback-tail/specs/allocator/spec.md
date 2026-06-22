# allocator Specification Delta

## MODIFIED Requirements

### Requirement: One priority combo per role, no weights

The system SHALL emit exactly one combo per role as an ordered endpoint list with
`strategy = priority` (index 0 = primary, 1..N = fallback); endpoint weights SHALL
NOT be calculated or stored. Combo members SHALL be partitioned into scored
endpoints and configured router endpoints (members of `auto_router_tail`). Scored
endpoints SHALL be ordered first, by AA quality ascending: the weakest
band-eligible endpoint is the primary (position 0) and the smartest scored
endpoint is the last scored position. Configured routers SHALL form a fallback
tail appended after the last scored endpoint, never interleaved with or placed
ahead of a scored endpoint, regardless of any score-like value. The tail SHALL be
ordered by `auto_router_tail` config order. A router SHALL be included in a role's
tail only when, for that role, it passes the access filter as free (the catalog
`cost` is not trusted), covers the role's required input modalities per its
config-declared `input`, meets the role's context-window minimum via the existing
`effective_context_window` hard filter, and passes probe/quota/breaker; a router
failing any of these is skipped for that role.
Scored endpoints SHALL be bounded by the scored-slot `per_pool_cap`; routers SHALL
NOT consume that cap and SHALL be bounded by the `auto_router_tail` length.

#### Scenario: Combo output
- GIVEN an allocated role
- WHEN its combo is emitted
- THEN it is an ordered priority list with no weights

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
- THEN `kilo-auto/free` is skipped for that role on its config-declared modalities
- AND `openrouter/free` is still appended

#### Scenario: Router never outranks a scored endpoint
- GIVEN a router whose computed score value would otherwise sort ahead of a
  scored endpoint
- WHEN the priority combo is built
- THEN the router is still placed after every scored endpoint

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
