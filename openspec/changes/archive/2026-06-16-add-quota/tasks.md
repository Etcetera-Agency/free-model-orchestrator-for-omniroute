# Implementation Tasks (TDD)

Write each test first (red) → green → refactor. Mock only the network boundary
with **recorded real** responses (project.md → Testing Strategy). PostgreSQL is
**real**. OmniRoute shapes: `../OmniRoute`.

## Fixtures to record (real)

- OmniRoute `POST /v1/search` with `gemini-grounded-search`: real `SearchResponse`
  with populated `answer.text` + grounding `results` (shape from
  `../OmniRoute/open-sse/handlers/search.ts`).
- Recorded Instructor completions for the `QuotaClaim` extraction: one valid, one
  malformed (to exercise repair/validation).
- OmniRoute `/api/pricing`, `/api/rate-limits` real responses.

## Tasks

- [x] 1. TEST: research builds natural-language date-aware queries and calls `/v1/search` with `gemini-grounded-search`; `answer.text` is persisted as a snapshot → implement search step.
- [x] 2. TEST: Instructor extraction → `QuotaClaim`; deterministic validation rejects amount≤0 / non-enum window / missing evidence; malformed completion triggers repair then reject → implement extraction + validator.
- [x] 3. TEST: summary-only activation caps confidence at `summary_confidence_cap`, sets `activated_by=summary`, opportunistic class; worsened quota → immediate safe mode → implement activation/change-detection.
- [x] 4. TEST: classifier order (zero-price→free_unlimited; rule+remaining→free_quota_available; promo; exclusions); trust order (live API beats models.dev); fail-closed to unknown_excluded → implement classifier.
- [x] 5. TEST: free_quota_available requires limit+remaining+reset+hard-stop+buffer (missing reset → not available) → implement preconditions.
- [x] 6. TEST: attribution capacity by status (confirmed full / inferred discounted / assumed_shared one / unknown zero); two unknown accounts add no capacity → implement attribution groups.
- [x] 7. TEST: merge on shared-counter evidence and split on confirmed independence each recalc allocation with audit → implement merge/split.
- [x] 8. TEST: `effective_remaining` math; exclude when no reliable value; hard-stop gating excludes endpoints without a guaranteed stop → implement quota manager counters + gating.
- [x] 9. TEST: reset path fetches live quota + reclassifies before probe; historical-source record without the reserve is rejected → implement reset + reserve guard.
