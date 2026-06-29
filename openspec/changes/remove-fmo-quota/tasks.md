# Implementation Tasks

- [ ] Verify cutover gate: OmniRoute accepts `fmo-pools/v1`, runs shadow solve, applies atomically, and is confirmed as the single combo writer before any destructive quota removal.
- [ ] Remove the `quota-research` and `quota-sync`/quota stages from the pipeline.
- [ ] Delete `src/fmo/quota_research.py`, `quota_manager.py`, `quota_normalize.py`, `quota_attribution.py`, `quota_recalibration.py`, `composition_stages/quota.py`.
- [ ] Delete `reference/prompts/quota-research.md`.
- [ ] Drop quota tables (`quota_*`, `role_quota_budgets`, `quota_pool_members`).
- [ ] Remove `tokens_per_request`, `tokens_per_request_recalibration_cron`, `llm_quota_research_call_limit` from `StartupConfig`.
- [ ] Remove now-dead quota tests; keep the suite green.
