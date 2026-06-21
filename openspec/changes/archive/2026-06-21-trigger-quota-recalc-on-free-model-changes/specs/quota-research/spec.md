# quota-research Specification

## MODIFIED Requirements

### Requirement: Primary quota source where OmniRoute is silent

The system SHALL use quota research as the primary source of quota for any
endpoint not covered by an official quota API or by OmniRoute (the free registry
and rate-limits cover only a subset of providers). It SHALL NOT re-search daily
an endpoint whose free access is already confirmed and whose rule is not stale.

Quota research SHALL run only when triggered by a **free-model change** since the
prior run, restricted to models reachable through an existing OmniRoute
connection: either (A) a newly detected confirmed-free model (models.dev
`free`/`0-cost` or free-provider), or (B) an existing model whose free/0-cost
status changed in either direction (free→paid, paid→free, 0-cost→priced). When no
such change is detected, the stage is a no-op for that run (the daily live
quota/probe/health path is unaffected). When triggered, the system SHALL perform
a **full recalc** that re-verifies every endpoint, overriding the not-stale daily
skip for that run, because one free-model change is a signal that other models'
policies may also have changed. OmniRoute `quotaTotal` (`GET /api/usage/quota`),
where present, SHALL be used as the known-limit input; search SHALL still
establish hard-stop behaviour for each endpoint.

#### Scenario: Endpoint absent from OmniRoute registry
- GIVEN an endpoint with no confirmed quota from any official API or OmniRoute
- WHEN the daily batch reaches quota research during a triggered recalc
- THEN that endpoint is researched to obtain a rule

#### Scenario: No new free model skips quota research
- GIVEN no free-model change (no new model and no free/0-cost status change) since
  the prior run
- WHEN the pipeline reaches quota research
- THEN the stage performs no `/v1/search` and reports an idempotent no-change
- AND the live quota/probe/health daily path still runs

#### Scenario: Changed free status triggers recalc
- GIVEN an existing model whose free/0-cost status changed since the prior run
  (free→paid or paid→free), reachable via an existing connection
- WHEN free-model-change detection runs
- THEN a full recalc is triggered and all endpoints are re-searched

#### Scenario: Recalc re-searches all on new free model
- GIVEN a new confirmed-free model reachable via an existing connection
- WHEN quota research runs
- THEN all endpoints are re-searched (the not-stale daily skip is overridden)
- AND an OmniRoute-known `quotaTotal` is used as the limit while search sets
  hard-stop behaviour

#### Scenario: New model outside our connections does not trigger
- GIVEN a new `free`/`0-cost` model whose provider has no OmniRoute connection
- WHEN new-free-model detection runs
- THEN no recalc is triggered by that model
