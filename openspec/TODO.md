# OpenSpec TODO

No deferred review follow-up work discovered.

## Active stage-wiring follow-up

- Implement and archive `wire-matching-access-stages`: wire
  `model-matching`, `quota-research`, and `access-classification`; replace the
  matching/access xfail placeholders with real effect assertions.
- Implement and archive `wire-probe-telemetry-stages`: wire `probing`,
  `telemetry-sync`, and `quota-sync`; replace the probe/telemetry xfail
  placeholders with real effect assertions.
- Implement and archive `wire-scoring-allocation-stages`: wire `role-scoring`,
  `allocation`, and `diff`; replace the scoring/allocation xfail placeholders
  with real effect assertions.
- Implement and archive `wire-apply-audit-stages`: wire `apply` and `audit`;
  replace the apply/audit xfail placeholders with real smoke, rollback, and
  audit effect assertions.

## Dropped (not needed for project essence)

- AA provider/detail/performance endpoints — the single free-tier endpoint
  (`GET /api/v2/language/models/free`) already provides every scoring input
  (`intelligence_index`, `coding_index`, `agentic_index`,
  `median_output_tokens_per_second`, `median_end_to_end_seconds`). YAGNI.
- models.dev retry/cache/ETag hardening — the orchestrator runs once per day, so
  ETag/conditional caching is pointless and retry is low-value; schema-drift
  reporting is already covered by `add-real-source-ingestion-tests`.
