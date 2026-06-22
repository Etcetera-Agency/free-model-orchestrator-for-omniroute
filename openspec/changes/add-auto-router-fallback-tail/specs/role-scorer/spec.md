# role-scorer Specification Delta

## ADDED Requirements

### Requirement: Configured routers are not AA-scored

The system SHALL recognize an endpoint as a router when its canonical model id
matches a configured `auto_router_tail` entry `id` (provider-flexible match).
Router membership SHALL be defined by this curated config list, NOT inferred from
a naming pattern, because routers are named inconsistently (`/free`, `-auto`,
`/auto`) and their catalog cost and capabilities are unreliable defaults. Each
entry carries its own declared `input` modalities; the context window is NOT
declared in config — routers reuse the existing `effective_context_window`
computation and context-window hard filter. Catalog parent/child links SHALL NOT
be collapsed: `mimocode/mimo-auto` is matched on its own id and is not treated as
an alias of its parent `mcode/mimo-auto`.
Because a router selects its underlying model dynamically per request, it has no
stable Artificial Analysis quality band. The system SHALL NOT compute an AA
quality subscore (`benchmark_fit`) for a router and SHALL NOT apply a
missing-quality uncertainty penalty to it. A router SHALL still be subject to
every non-quality eligibility hard filter (access as free, basic probe, usable
quota, model match, closed breaker, required capabilities, context-window
minimum). The membership SHALL be exposed on the endpoint record consumed by
allocation.

#### Scenario: Configured router is recognized
- GIVEN `auto_router_tail` contains `openrouter/free`
- AND an endpoint whose canonical model is `openrouter/free`
- WHEN router membership is evaluated
- THEN the endpoint is recognized as a router
- AND the provider prefix and letter case are ignored in the match

#### Scenario: Unlisted model is not a router
- GIVEN `auto_router_tail` does not contain `google/gemini-2.5-flash`
- WHEN router membership is evaluated for that endpoint
- THEN the endpoint is not recognized as a router

#### Scenario: Child router is independent of its parent
- GIVEN `auto_router_tail` contains `mimocode/mimo-auto` but not its catalog
  parent `mcode/mimo-auto`
- WHEN router membership is evaluated for both endpoints
- THEN only `mimocode/mimo-auto` is recognized as a router
- AND the parent link is not used to collapse or alias the two

#### Scenario: Router skips AA quality scoring
- GIVEN an eligible router endpoint with no AA quality indices
- WHEN role scoring runs
- THEN no `benchmark_fit` term is contributed
- AND no missing-quality uncertainty penalty is applied

#### Scenario: Router still honors non-quality filters
- GIVEN a router endpoint whose breaker is not closed
- WHEN scoring eligibility runs
- THEN it is rejected with a breaker reason like any other endpoint
