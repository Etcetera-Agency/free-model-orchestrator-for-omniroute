-- v3.28 -- remove retired FMO matching/probing/discovery ownership.

DROP TABLE IF EXISTS combo_review_runs CASCADE;
DROP TABLE IF EXISTS web_cookie_static_candidates CASCADE;
DROP TABLE IF EXISTS artificial_analysis_threshold_versions CASCADE;
DROP TABLE IF EXISTS artificial_analysis_index_migrations CASCADE;
DROP TABLE IF EXISTS artificial_analysis_model_metrics CASCADE;
DROP TABLE IF EXISTS free_provider_quality_observations CASCADE;
DROP TABLE IF EXISTS free_model_definitions CASCADE;
DROP TABLE IF EXISTS free_provider_definitions CASCADE;
DROP TABLE IF EXISTS free_provider_registry_snapshots CASCADE;
DROP TABLE IF EXISTS account_discovery_snapshots CASCADE;
DROP TABLE IF EXISTS endpoint_health_observations CASCADE;
DROP TABLE IF EXISTS endpoint_probes CASCADE;
DROP TABLE IF EXISTS model_match_candidates CASCADE;
DROP TABLE IF EXISTS endpoint_access_states CASCADE;
DROP TABLE IF EXISTS role_scores CASCADE;
DROP TABLE IF EXISTS provider_catalog_snapshots CASCADE;
DROP TABLE IF EXISTS provider_endpoints CASCADE;
DROP TABLE IF EXISTS provider_accounts CASCADE;
DROP TABLE IF EXISTS providers CASCADE;
DROP TABLE IF EXISTS canonical_models CASCADE;
DROP TABLE IF EXISTS role_bootstrap_profiles CASCADE;
DROP TABLE IF EXISTS role_usage_observations CASCADE;
DROP TABLE IF EXISTS agent_execution_observations CASCADE;
DROP TABLE IF EXISTS role_usage_dependencies CASCADE;
DROP TABLE IF EXISTS agent_role_usage_profiles CASCADE;
DROP TABLE IF EXISTS agents CASCADE;
