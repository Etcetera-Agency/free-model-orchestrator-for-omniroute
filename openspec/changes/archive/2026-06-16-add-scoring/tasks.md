# Implementation Tasks (TDD)

Write each test first (red) → green → refactor. Mock only the network boundary
with **recorded real** responses (project.md → Testing Strategy). PostgreSQL is
**real**. OmniRoute shapes: `../OmniRoute`.

## Fixtures to record (real)

- OmniRoute `POST /v1/providers/{provider}/chat/completions` probe response (200,
  plus a `402` and a `429`).
- OmniRoute telemetry: `/api/monitoring/health`, `/api/telemetry/summary`,
  `/api/resilience`, `/api/usage/*` real responses (provider- and endpoint-level).
- Artificial Analysis `/api/v2/language/models` item (real `evaluations.artificial_analysis_*`).

## Tasks

- [x] 1. TEST: probe runs only after free classification + reserved capacity; unconfirmed endpoint is not probed → implement gate.
- [x] 2. TEST: probe uses dedicated provider route + explicit model + no-cache; capability suites run only when claimed → implement suites.
- [x] 3. TEST: error map (402 exclude+research, 429→quota mgr, 401/403 auth-degraded); promotion to active only on passed basic probe + valid free + closed breaker → implement.
- [x] 4. TEST: telemetry tags latency granularity (provider vs endpoint) and never passes provider p95 as endpoint; degraded on 3 consecutive errors without disabling siblings → implement telemetry sync.
- [x] 5. TEST: eligibility filter rejects unmatched / open-breaker / insufficient-quota before scoring → implement filter.
- [x] 6. TEST: AA v1 P5/P95 clipped min-max, inverted latency; one missing metric redistributes weight + uncertainty penalty; all-three missing → unknown → implement AA subscore.
- [x] 7. TEST: latency source priority endpoint>provider>AA; score excludes price; unchanged `input_state_hash` skips recompute → implement scorer.
- [x] 8. TEST: context = min of known sources; below role minimum excluded; far-above gets no bonus/extra combo; unknown excluded unless override → implement context eligibility.
- [x] 9. TEST: quality gate is a hard pre-filter; missing metric → unverifiable excluded (unless override); major index change → keep current combo, no new plan → implement quality gate.
