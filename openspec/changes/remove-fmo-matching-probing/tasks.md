# Implementation Tasks

- [ ] Verify cutover gate: OmniRoute accepts `fmo-pools/v1`, runs shadow solve, applies atomically, and is confirmed as the single combo writer before any destructive matching/probing removal.
- [ ] Remove the `model-matching` and `probing` stages from the pipeline.
- [ ] Delete `src/fmo/matcher.py`, `artificial_analysis.py`, `aa_migration.py`, `aa_index_runtime.py`, `scoring.py`, `probes.py`.
- [ ] Delete the discovery set: `scanner.py`, `provider_sweep.py`, `candidates.py`, `model_registration.py`, `accounts.py`, `access.py`, `smart_review.py`, `web_cookie.py`.
- [ ] Trim `telemetry.py` (drop `sync_live_telemetry`/`degrade_endpoint`/`_provider_metrics`/`_model_metrics`); keep consumer/demand counters only.
- [ ] Trim `state.py` (drop `EndpointState`/`ComboState` + transitions); role state stays in `role_lifecycle.py`.
- [ ] Trim `composition.py` (`sweep_provider_models`, `_refresh_live_catalog`) and retired `composition_stages/*`.
- [ ] Drop provider/model/endpoint/AA/free-definition/web-cookie tables; keep agents/roles/usage/audit/`published_generations`.
- [ ] Remove `llm_bootstrap_*`, `llm_smart_review_call_limit` from `StartupConfig`.
- [ ] Remove now-dead tests; update `README.md` scope (publisher-only) and `openspec/project.md`.
