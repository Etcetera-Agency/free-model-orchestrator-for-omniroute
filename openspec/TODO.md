# OpenSpec TODO

## Deferred follow-up

- Fingerprint-backed account quota pools: implement
  `update-fingerprint-account-quota-pools` so any provider connection with
  `providerSpecificData.fingerprints` expands into independent
  provider-account quota pools without hard-coding provider names,
  allocation/combos can use the multiplied per-account capacity, and the
  matching `account-discovery::*` entries are removed from
  `tests/spec_coverage_pending.txt`.

## Dropped (not needed for project essence)

- AA provider/detail/performance endpoints — the single free-tier endpoint
  (`GET /api/v2/language/models/free`) already provides every scoring input
  (`intelligence_index`, `coding_index`, `agentic_index`,
  `median_output_tokens_per_second`, `median_end_to_end_seconds`). YAGNI.
- models.dev retry/cache/ETag hardening — the orchestrator runs once per day, so
  ETag/conditional caching is pointless and retry is low-value; schema-drift
  reporting is already covered by `add-real-source-ingestion-tests`.
