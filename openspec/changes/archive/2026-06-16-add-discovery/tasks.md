# Implementation Tasks (TDD)

Write each test first (red) → green → refactor. Mock only the network boundary
with **recorded real** responses (project.md → Testing Strategy). PostgreSQL is
**real**. OmniRoute shapes: `../OmniRoute`.

## Fixtures to record (real)

- models.dev `api.json`/`catalog.json` slice: a zero-cost, a priced, and a no-`cost` provider→model entry.
- OmniRoute `/api/providers`, `/api/providers/{id}/models` real responses.
- OmniRoute `/api/free-models`, `/api/free-provider-rankings`, `/api/free-tier/summary` (fields incl. `poolKey`).
- OmniRoute `/api/rate-limits` real response (for account identity).

## Tasks

- [x] 1. TEST: candidate filter flags zero-cost and standalone-`free` per provider→model, never on missing `cost`, no substring false-positives → implement filter + reason codes.
- [x] 2. TEST: same model id priced differently per provider yields a candidate only for the zero-cost provider → implement per-provider cost read.
- [x] 3. TEST: scanner snapshots by `catalog_hash` and skips diff on unchanged hash → implement snapshot.
- [x] 4. TEST: diff emits `provider_model_*` events; new endpoint upserts as discovered/access_pending/not_run → implement upsert.
- [x] 5. TEST: model marked removed only after two successful fetches ≥5min apart; a failed fetch never marks removed → implement false-removal guard.
- [x] 6. TEST: capacity = sum of independent pools (shared upstream → one; independent → sum) → implement account grouping.
- [x] 7. TEST: grouping order resolves to shared on unproven independence; `/api/rate-limits` down reuses last grouping → implement grouping + fallbacks.
- [x] 8. TEST: `poolKey` shared across models counted once at max budget; rankings never used for discovery; web-cookie excluded from refresh → implement free registry sync.
- [x] 9. TEST: matcher ordered resolution; forbidden auto-merges (base/instruct, thinking, snapshots) rejected; auto-use only ≥0.90; provider context overrides canonical → implement matcher.
