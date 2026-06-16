# Implementation Tasks (TDD)

Write each test first (red) → green → refactor. Mock only the network boundary
with **recorded real** responses (project.md → Testing Strategy). PostgreSQL is
**real**. OmniRoute shapes: `../OmniRoute`.

## Fixtures to record (real)

- OmniRoute combo endpoints `/api/combos*` (list/get/create/update) — capture the
  exact payloads from the running version; shapes via `../OmniRoute` (note the
  generic `/api/combos*` family must be pinned by an integration fixture).
- OmniRoute `POST /v1/chat/completions` smoke-test response via a combo model name.
- Hermes `state.db` rows (`sessions.model/input_tokens/output_tokens/api_call_count`)
  and `cron/jobs.json` for demand projection.

## Tasks

- [x] 1. TEST: agent runs projected to each quota reset; agent→role bindings summed; shared-role DAG expansion; cycle rejected → implement demand aggregation.
- [x] 2. TEST: expected vs protected demand; 20% historical reserve applied exactly once (base/multiplier/reserved recorded) → implement.
- [x] 3. TEST: cold start never zero; source priority schedule>bootstrap>role>global; blended transition → implement cold start.
- [x] 4. TEST: global allocation; a shared endpoint is not promised in full to multiple roles; heavy-role separation enforced → implement allocator core.
- [x] 5. TEST: one priority combo per role, ordered, no weights; per-pool/per-group caps → implement combo build.
- [x] 6. TEST: oversubscription_ratio>1 blocks the plan; degraded modes set instead of paid fallback → implement validation + degraded modes.
- [x] 7. TEST: stability — unchanged eligible set / sub-threshold drift keeps current order → implement anti-churn.
- [x] 8. TEST: applier manages only `fmo-` combos; transactional apply (lock, re-read, hash check, snapshot, apply, read-back, smoke) on real recorded combo payloads → implement applier.
- [x] 9. TEST: smoke-test failure restores snapshot + marks run failed; manual `fmo-` drift creates a conflict, not an overwrite → implement rollback + drift.
- [x] 10. TEST: `sync_runs` + `change_log` with before/after/reason/source_refs (real Postgres); rollback reverts a run's combos while catalog snapshots remain → implement audit/rollback.
