# Implementation Tasks

- [x] Verify cutover gate: OmniRoute accepts `fmo-pools/v1`, runs shadow solve, applies atomically, and is confirmed as the single combo writer before any destructive quota removal.
  - Gate not live on 2026-06-29; user explicitly waived the gate for this slice and asked to implement pure FMO specs first. Follow-up remains in repo TODO.
- [x] Remove the `quota-research` and `quota-sync`/quota stages from the pipeline.
- [x] Delete `src/fmo/quota_research.py`, `quota_manager.py`, `quota_normalize.py`, `quota_attribution.py`, `quota_recalibration.py`, `composition_stages/quota.py`.
- [x] Delete `reference/prompts/quota-research.md`.
- [x] Drop quota tables (`quota_*`, `role_quota_budgets`, `quota_pool_members`).
- [x] Remove `tokens_per_request`, `tokens_per_request_recalibration_cron`, `llm_quota_research_call_limit` from `StartupConfig`.
- [x] Remove now-dead quota tests; keep the suite green.
