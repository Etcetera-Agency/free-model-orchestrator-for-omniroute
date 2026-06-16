# Implementation Tasks (TDD)

Write each test first (red) → green → refactor. Mock only the network boundary
with **recorded real** responses (project.md → Testing Strategy). PostgreSQL is
**real**. OmniRoute shapes: `../OmniRoute`.

## Fixtures to record (real)

- Recorded Instructor `ComboReview` completions: one with valid add/remove/move,
  one with a forbidden op (weights/strategy), one malformed.
- Recorded Instructor `MigrationProposal` completion (valid + one violating combo
  size / capacity).
- Artificial Analysis responses for old vs new `index_version` (to trigger migration).
- OmniRoute `POST /v1/chat/completions` for the smoke test after rollout.

## Tasks

- [x] 1. TEST: reviewer makes one structured call; a forbidden op (weights/strategy/quota/gate) is rejected → implement reviewer call + op allowlist.
- [x] 2. TEST: each diff validated independently on a copy; one invalid diff is logged+skipped, others kept; no repair loop → implement diff application.
- [x] 3. TEST: reviewer unavailable/failed/no-valid-diffs → deterministic combo applied; `/api/combos/test` never called → implement fail-open + trigger gate.
- [x] 4. TEST: new AA `index_version` freezes old thresholds, keeps current combos, creates a migration, stops production recalculation → implement detection.
- [x] 5. TEST: migration agent selects highest new-`intelligence_index` model; Instructor `MigrationProposal`; percentile mapping reference-only → implement agent.
- [x] 6. TEST: deterministic validation (schema, combo size, quality, capacity) + dry-run; rollout only after approval → implement validation + approval gate.
- [x] 7. TEST: no migration model available → production thresholds/combos unchanged; smoke-test failure after rollout → rollback → implement fallbacks + rollback.
