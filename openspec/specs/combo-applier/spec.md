# combo-applier Specification

## Purpose
TBD - created by archiving change add-allocation. Update Purpose after archive.
## Requirements
### Requirement: Manage only fmo- combos

The system SHALL manage only OmniRoute combos whose name carries the configured
managed prefix (`fmo-`) and SHALL NOT modify combos outside that prefix. When
OmniRoute returns a generated UUID `id` plus a human combo `name`, the system
SHALL use the prefixed `name` as the managed combo key for diff/apply, and SHALL
use the live `id` as the management write route id when that id is present.

#### Scenario: Foreign combo
- GIVEN an OmniRoute combo without the `fmo-` prefix
- WHEN the applier runs
- THEN that combo is left untouched

#### Scenario: Live UUID combo id with managed name
- GIVEN OmniRoute returns a combo with UUID `id` and `name = fmo-grid-int-med`
- WHEN the applier reads the live combo set
- THEN it treats `fmo-grid-int-med` as the managed combo key
- AND it writes that combo through the live UUID route id
- AND it does not synthesize `fmo-fmo-grid-int-med`

### Requirement: Transactional apply with smoke test

The system SHALL apply changes under the `combo_apply` advisory lock by:
re-reading current state, verifying its hash is unchanged, saving a snapshot,
applying create/update, reading the combo back, comparing to desired, running a
smoke test via the combo model name, and only then committing the change record.
The diff snapshot SHALL compare and persist the last live OmniRoute combo state
against the desired structured combo member list, and apply only managed `fmo-*`
combos whose live baseline still matches the saved structured `before` state.
Applied combo payloads SHALL preserve priority order and SHALL be sent to
OmniRoute as structured model steps when provider/account identity is known.
Drift, unsafe preconditions, smoke-test failure, and rollback behavior SHALL
remain deterministic and fail closed.

#### Scenario: State changed under us
- GIVEN the current combo hash changed since planning
- WHEN apply starts
- THEN the apply aborts rather than overwrite the newer state

#### Scenario: Structured combo steps applied
- **GIVEN** an allocation target includes `providerId`, `model`, and
  `connectionId`
- **WHEN** apply updates the managed combo
- **THEN** the OmniRoute `PUT /api/combos/{id}` payload contains structured model
  steps preserving those fields

#### Scenario: Endpoint ids retained for audit
- **WHEN** the diff snapshot stores structured `before` and `after` members
- **THEN** it also stores endpoint-id audit fields so rollback/audit can explain
  which provider endpoint each member came from

#### Scenario: Drift guard uses structured baseline
- **GIVEN** the live structured combo differs from the saved structured `before`
  state
- **WHEN** apply runs
- **THEN** apply fails as `combo_drift_detected` and does not overwrite the combo

### Requirement: Rollback on failure

The system SHALL restore the pre-change baseline, re-read, smoke-test the restored
version and mark the run failed when apply or smoke test fails. The pre-change
baseline SHALL be the live combo state captured immediately before the mutation
(the same read used for the hash/precondition check), NOT the `before` value
recorded at diff time. If the live state captured at apply time differs from the
diff-time `before`, the applier SHALL follow the drift-protection path (create a
conflict / require force) instead of overwriting. Every restore/revert combo
write SHALL carry an `Idempotency-Key` derived from the restored combo state,
matching the convention used for forward apply writes, so a retried revert is a
no-op rather than a double-apply. This applies to both the in-apply rollback
after a smoke failure and the top-level `rollback` command.

#### Scenario: Smoke test fails
- GIVEN the post-apply smoke test fails
- WHEN failure is handled
- THEN the combo is restored to the live state captured immediately before the
  mutation and the run is marked failed

#### Scenario: Live state diverged from diff-time before
- GIVEN the live combo state at apply time differs from the `before` recorded at
  diff time
- WHEN apply starts
- THEN the applier follows the drift-protection path rather than overwriting with
  the stale diff-time value

#### Scenario: Revert write carries an idempotency key
- GIVEN a rollback restores a combo to its pre-change baseline
- WHEN the revert `PUT /api/combos/{id}` is issued
- THEN it carries an `Idempotency-Key` derived from the restored state
- AND a retried revert with the same key is not applied twice

### Requirement: Drift protection and anti-churn

The system SHALL detect manual edits to an `fmo-` combo, refuse to overwrite them
automatically, create a conflict requiring force/override, and respect anti-churn
limits (minimum improvement, max changes per run, no apply during incomplete
telemetry sync).

#### Scenario: Manual edit detected
- GIVEN a human changed an `fmo-` combo outside the service
- WHEN the applier detects the drift
- THEN it creates a conflict and does not overwrite without force

### Requirement: Apply preconditions evaluated at the entrypoint

The entrypoint SHALL compute apply preconditions by evaluating the apply guard —
database availability, a saved snapshot, a valid desired state, quota safety, and
a passing probe/smoke result — and SHALL pass that computed value into CLI
dispatch instead of a hardcoded value. The evaluation SHALL fail closed: any
unknown, stale, or unavailable input yields preconditions `False`. The
entrypoint's quota and probe safety SHALL be scoped to the desired endpoint ids
from the latest `diff` snapshots and SHALL use the same request-window hard-stop
quota rules as the apply stage.

#### Scenario: Failing guard input blocks apply
- **WHEN** any apply-guard input is failing, unknown, or stale at the entrypoint
- **THEN** apply preconditions are `False`
- **AND** `apply` exits with code 5 (unsafe) and changes nothing

#### Scenario: Healthy guard inputs allow apply
- **WHEN** every apply-guard input is healthy at the entrypoint
- **THEN** apply preconditions are `True`
- **AND** `apply` is allowed to proceed through the runner's gating

#### Scenario: Diff-scoped request-window guard allows apply
- **WHEN** the latest diff targets an endpoint with researched minute/hour
  hard-stop request quota and a fresh passing probe
- **AND** unrelated endpoint probes or old probe attempts have failed
- **THEN** entrypoint preconditions are still derived from the diff target
- **AND** `apply` is allowed to proceed through the runner's gating

### Requirement: Production apply invokes the real smoke path

The composed production runtime SHALL invoke the combo applier and its
transactional smoke test when the `apply` stage runs; it SHALL NOT report a
fabricated combo-test signal. The smoke test SHALL exercise the applied `fmo-`
combos through the existing OmniRoute path and SHALL NEVER call
`/api/combos/test`. When the smoke test fails, the runtime SHALL roll back the
applied diff.

The smoke decision SHALL be derived from the OmniRoute-compatible response, not
from a fabricated body-level field. A smoke POST that completes without raising
(HTTP 2xx, enforced by the OmniRoute client) and returns a non-empty assistant
message (`choices[0].message.content`) or non-empty streamed text/SSE content
SHALL be treated as a smoke pass. The smoke request SHALL set `stream=true` so
providers that require streaming use their live-compatible route. A smoke POST
that raises `OmniRouteRequestError` (non-2xx HTTP) or returns an empty or missing
assistant/text content SHALL be treated as a smoke failure that triggers
rollback. The smoke decision SHALL NOT read a top-level `status_code` field from
the response body.

#### Scenario: Production apply smoke-tests applied combos
- **WHEN** the production `apply` stage applies a combo diff
- **THEN** the transactional smoke test runs against the applied `fmo-` combos
- **AND** the runtime never calls `/api/combos/test`

#### Scenario: Fabricated smoke signal rejected
- **WHEN** the apply adapter reports the combo-test signal
- **THEN** the signal reflects whether the real smoke test ran
- **AND** a hardcoded or fabricated combo-test signal fails the executable suite

#### Scenario: Smoke pass derived from OpenAI-compatible body
- GIVEN a smoke POST returns HTTP 2xx with a non-empty
  `choices[0].message.content`
- WHEN the smoke decision is computed
- THEN the smoke passes without reading any body-level `status_code` field

#### Scenario: Smoke pass derived from non-empty SSE text
- GIVEN a smoke POST returns HTTP 2xx with non-empty streamed text content
- WHEN the smoke decision is computed
- THEN the smoke passes
- AND the smoke request includes `stream=true`

#### Scenario: Empty completion is a smoke failure
- GIVEN a smoke POST returns HTTP 2xx but the assistant message content is empty
  or missing
- WHEN the smoke decision is computed
- THEN the smoke fails and the applied diff is rolled back

#### Scenario: Non-2xx smoke response is a smoke failure
- GIVEN the smoke POST raises `OmniRouteRequestError` for a non-2xx HTTP status
- WHEN the smoke decision is computed
- THEN the smoke fails and the applied diff is rolled back rather than crashing

### Requirement: Apply stage derives quota and probe safety from persisted state

The production `apply` stage SHALL compute the `quota_safe` and `probes_passed`
apply-precondition inputs from persisted repository state for the endpoints in
the combos it is about to apply, and SHALL NOT use hardcoded values. `quota_safe`
SHALL be true for an endpoint only when it is confirmed-free, hard-stop-capable,
has a fresh passing probe, has a **known daily budget** — a research/calibration
capacity in request-equivalents per day above the safety buffer — and a **fresh
live liveness signal** showing `percentRemaining` above the configured floor
(`APPLY_MIN_PERCENT_REMAINING`) and not currently locked out. The learned live
request rate (`quotaTotal`/`quotaUsed`) is a sub-day reactive gate enforced by
OmniRoute and SHALL NOT be used as the daily-budget capacity. The safety buffer
SHALL be a configured positive floor, not an implicit `0`. Liveness SHALL come
from a live quota observation, not from a value assumed at classification time: an
assumed remaining synthesized at classification without any live observation SHALL
NOT satisfy `quota_safe`, except when it is tied to a researched active hard-stop
quota rule whose only known capacity is a sub-day request window (minute/hour)
and the effective request remaining is above the configured safety buffer. A
future `resetAt` SHALL mean the endpoint is currently locked out and excluded; a
null `resetAt` SHALL NOT by itself fail the gate (it is the healthy,
not-rate-limited state). `probes_passed` SHALL be true only when
every endpoint in the desired combos has a passing, non-stale probe/smoke result.
The evaluation SHALL fail closed: any missing, unknown, assumed, stale, exhausted,
or locked-out input yields the corresponding value `False`, the stage returns
`unsafe_to_apply` (exit 5), and no combo is mutated.

#### Scenario: Failing quota evidence blocks the apply stage
- **WHEN** an endpoint in a desired `fmo-` combo has a failing, missing, or stale
  quota-safety record at apply time
- **THEN** the stage derives `quota_safe` as `False`
- **AND** the stage returns `unsafe_to_apply` (exit 5) and mutates no combo

#### Scenario: Failing probe evidence blocks the apply stage
- **WHEN** an endpoint in a desired `fmo-` combo lacks a passing, non-stale
  probe/smoke result at apply time
- **THEN** the stage derives `probes_passed` as `False`
- **AND** the stage returns `unsafe_to_apply` (exit 5) and mutates no combo

#### Scenario: Confirmed safety allows the apply stage
- **WHEN** every endpoint in the desired combos is confirmed-free, hard-stop,
  freshly probed, has a known daily budget above the buffer, and a fresh liveness
  signal above the floor that is not locked out
- **THEN** both derived inputs are `True`
- **AND** the apply stage proceeds to mutate the combos

#### Scenario: Assumed remaining does not satisfy the apply gate
- **WHEN** an endpoint's only quota evidence is an assumed remaining synthesized
  at classification time, with no live liveness observation or researched
  request-window hard-stop rule
- **THEN** the stage derives `quota_safe` as `False` for that endpoint
- **AND** the stage returns `unsafe_to_apply` (exit 5) and mutates no combo

#### Scenario: Request-window hard-stop quota can satisfy apply safety
- **WHEN** a confirmed-free endpoint has a researched active hard-stop quota rule
  for requests per minute or hour
- AND the endpoint has assumed request remaining above the safety buffer
- **THEN** the stage derives `quota_safe` as `True` without requiring a daily or
  monthly live budget
- AND a future reset timestamp for that request window does not fail the gate
  while remaining capacity is still above the buffer
- AND a live liveness overlay with zero percent remaining or a future reset does
  not fail that request-window gate while researched request capacity remains
  above the buffer

#### Scenario: Zero safety buffer does not satisfy the apply gate
- **WHEN** an endpoint's daily-budget record carries no safety buffer and its
  capacity does not exceed the configured minimum buffer
- **THEN** the stage treats the buffer as the configured positive floor, not `0`
- **AND** derives `quota_safe` as `False` rather than passing on a zero buffer

#### Scenario: Research budget with healthy liveness passes
- **WHEN** a confirmed-free, hard-stop, freshly probed endpoint has a
  research/calibration daily budget above the buffer and a fresh `percentRemaining`
  above the floor that is not locked out
- **THEN** the stage derives `quota_safe` as `True`
- **AND** the apply stage proceeds to mutate the combos

#### Scenario: Exhausted or locked-out endpoint is excluded
- **WHEN** an endpoint's fresh liveness shows `percentRemaining` at or below the
  floor, or its `resetAt` is in the future
- **THEN** the stage derives `quota_safe` as `False` for that endpoint
- **AND** the stage returns `unsafe_to_apply` (exit 5) and mutates no combo

#### Scenario: Endpoint with null reset is not rejected
- **WHEN** a confirmed-free, hard-stop, freshly probed endpoint has a known daily
  budget, healthy liveness, and `resetAt = null`
- **THEN** the null `resetAt` does not fail the gate
- **AND** the stage derives `quota_safe` as `True`

### Requirement: Multi-combo apply is all-or-nothing

When an apply run mutates more than one `fmo-` combo, the run SHALL be
all-or-nothing. No combo SHALL be mutated in OmniRoute without a persisted record
that makes it recoverable for rollback and visible to the `audit` stage. If any
combo in the run fails its smoke test, every combo already applied in that run
SHALL be restored to its pre-change state before the stage returns. The stage
SHALL report `apply_failed_rolled_back` (exit 6) when the partial apply is fully
rolled back, and `rollback_failed` (exit 7) when any restore call fails.

#### Scenario: Later combo failure rolls back earlier applied combos
- **GIVEN** a run that applies combo A successfully and then fails the smoke test
  on combo B
- **WHEN** the failure is handled
- **THEN** both combo A and combo B are restored to their pre-change state in
  OmniRoute
- **AND** the stage reports `apply_failed_rolled_back` (exit 6)

#### Scenario: No combo is mutated without a persisted record
- **WHEN** a combo is successfully applied in a multi-combo run
- **THEN** a persisted record for that combo exists before the next combo is
  applied, so a subsequent failure can roll it back and `audit` can see it

#### Scenario: Restore failure during partial rollback
- **GIVEN** a partial apply must be rolled back and a restore call raises
- **WHEN** the rollback runs
- **THEN** the stage reports `rollback_failed` (exit 7)

### Requirement: Rebalance only existing combos; never create or delete

The system SHALL rebalance the membership of OmniRoute combos that already exist
in the live combo set and SHALL NOT create or delete any combo. Combo existence
SHALL be decided only from the live OmniRoute combo set
(`_read_current_combos`), never from persisted state, because the operator may
create a combo by hand and a known combo may have been removed upstream.

A desired `fmo-` change whose combo id is absent from the live set SHALL be
skipped and reported as `unmanaged_combo`; skipping an absent combo SHALL NOT
fail the run, and every other present combo in the same apply SHALL still be
rebalanced. The applier SHALL issue no DELETE on any path (success, drift, or
rollback). Drift protection, the smoke path, rollback, and the `fmo-` scoping all
remain in force for combos that exist.

#### Scenario: Non-existent combo is not created
- GIVEN a desired `fmo-` diff whose combo id is absent from the live OmniRoute
  combo set
- WHEN apply runs
- THEN no `POST /api/combos/{id}` is issued for that combo
- AND it is reported as `unmanaged_combo`

#### Scenario: Absent combo is skipped without failing the run
- GIVEN one desired combo that exists and one that is absent
- WHEN apply runs
- THEN the existing combo is rebalanced and smoke-tested
- AND the absent combo is skipped, and the run is not failed by the skip

#### Scenario: Empty target diff is skipped without deleting combo members
- GIVEN a latest diff for an existing managed combo has an empty desired target
  list
- WHEN apply runs
- THEN the combo is skipped and reported as an empty-target skip
- AND no write is sent that would delete every existing combo member

#### Scenario: Latest diff per role is authoritative
- GIVEN an older diff snapshot exists for a previous managed combo id of the
  same role
- AND a newer diff snapshot exists for the current managed combo id
- WHEN apply runs
- THEN only the newest diff for that role is evaluated
- AND the older combo id is not reported as an unmanaged combo

#### Scenario: Combos are never deleted
- GIVEN any apply outcome (success, drift, or rollback)
- WHEN apply runs
- THEN no combo delete request is issued to OmniRoute

### Requirement: Apply uses management combo API through the live bridge

The combo applier SHALL read and write live OmniRoute combo state through the
management combo API exposed by the live API bridge. Apply SHALL read the live
combo set with `GET /api/combos` before mutation, SHALL update only existing
`fmo-` combos through the management write route under `/api/combos/{id}`, and
SHALL preserve drift protection, idempotency, read-back verification, smoke
testing through the OpenAI-compatible combo model, rollback, and rebalance-only
behavior.

#### Scenario: Apply reads combos through management API bridge
- GIVEN the apply stage is configured with the live API bridge base URL
- WHEN apply starts
- THEN it reads the live combo set through `GET /api/combos`
- AND it uses that response as the source of truth for existing managed combos

#### Scenario: Apply writes existing combos through management API bridge
- GIVEN an `fmo-` combo exists in the live combo set
- WHEN apply rebalances that combo
- THEN it sends the membership update through the management route under
  `/api/combos/{id}`
- AND it reads the combo back through the management API before reporting
  success

### Requirement: Public combo projection is never used for management apply

FMO SHALL NOT use `/v1/combos` or any other public/projected combo endpoint to
read, write, validate, or roll back managed combo state. Public combo projections
are not a substitute for OmniRoute management auth, management route validation,
or persisted operator-owned combo state.

#### Scenario: Public combo projection is never used for management apply
- GIVEN combo apply needs to read, write, validate, or roll back live combo
  state
- WHEN the applier performs the operation
- THEN every combo-management operation uses `/api/combos*`
- AND no request is sent to `/v1/combos`
