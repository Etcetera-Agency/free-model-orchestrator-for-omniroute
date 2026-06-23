# Change: Update AA Index Migration Inspector

## Why

The `aa-index-migration` Instructor site is specified as a threshold migration
inspector, but the runtime currently sends only the selected model JSON as the
prompt context. The external prompt file, role/capacity context, operational
validation details, repair loop, and rollout-time validation are not wired into
the production path. This makes the advisory output too under-informed and lets
approved proposals reach rollout without the full deterministic safety checks
described by the spec.

## What Changes

- Load `reference/prompts/aa-index-migration.md` through the shared prompt
  assembly path and interpolate concrete migration context.
- Build a deterministic migration context from persisted AA metrics, active
  threshold versions, role requirements, current combos, quota/liveness state,
  endpoint capabilities, and percentile mappings.
- Fix the production model-selection path so `aa-index analyze` uses the shared
  runtime resolver with fresh live quota checks instead of a resolver-less
  duplicate pre-check.
- Replace raw role dictionaries with typed Pydantic response models for the
  machine-used fields only: per-role metric and normalized `threshold_value`.
  Optional rationale may be retained in raw LLM audit payloads, but it SHALL NOT
  drive rollout decisions.
- Add operational validation and bounded repair retries before persisting a
  proposal; invalid repaired attempts end as manual review/fail-closed without
  mutating production thresholds or combos.
- Re-run deterministic validation at rollout time and persist a baseline audit
  snapshot for rollback/explainability.
- Add/update executable spec-bound tests and anchor comments for the migration
  context builder, validator, and rollout gate.

## Impact

- Affected specs: `aa-index-migration`, `llm-runtime`.
- Affected code: `src/fmo/aa_migration.py`, `src/fmo/aa_index_runtime.py`,
  `src/fmo/llm_runtime.py` if prompt-path plumbing needs config support,
  repository/query helpers, fixtures, and related tests.
- Affected data: `artificial_analysis_index_migrations.baseline_snapshot_json`,
  `threshold_proposal_json`, and `llm_proposal_json` become meaningful audit
  payloads rather than minimal placeholders.
