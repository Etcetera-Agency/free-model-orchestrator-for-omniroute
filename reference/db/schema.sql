-- Free Model Orchestrator — consolidated current-state schema (v3.19).
--
-- This file is the single source of truth for a FRESH install: every table is
-- created with its full, current column set (no post-hoc ALTER ADD COLUMN for
-- tables defined here). To UPGRADE a database created by an older version,
-- apply the ordered scripts in db/migrations/ instead.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE sync_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_type text NOT NULL,
  trigger text NOT NULL,
  status text NOT NULL,
  code_version text NOT NULL,
  config_hash text NOT NULL,
  omniroute_version text,
  started_at timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz,
  error_json jsonb
);

CREATE UNIQUE INDEX sync_runs_active_lock_name_idx
  ON sync_runs (trigger)
  WHERE run_type = 'lock'
    AND status = 'held'
    AND finished_at IS NULL;

CREATE TABLE providers (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  omniroute_instance_id text NOT NULL,
  omniroute_provider_id text NOT NULL,
  provider_type text NOT NULL,
  display_name text,
  enabled boolean NOT NULL DEFAULT true,
  provider_group text,
  raw_config_hash text,
  first_seen_at timestamptz NOT NULL DEFAULT now(),
  last_seen_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (omniroute_instance_id, omniroute_provider_id)
);

CREATE TABLE provider_accounts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  provider_id uuid NOT NULL REFERENCES providers(id),
  omniroute_connection_id text,
  external_account_ref text,
  upstream_account_ref text,
  account_type text NOT NULL DEFAULT 'credential',
  auth_type text,
  connection_fingerprint text,
  quota_independence_status text NOT NULL DEFAULT 'assumed_shared'
    CHECK (quota_independence_status IN (
      'confirmed', 'inferred', 'assumed_shared', 'unknown'
    )),
  -- Quota scope identity (v3.4): how the upstream quota is partitioned.
  quota_scope_type text,
  quota_scope_key text,
  provider_instance_key text,
  enabled boolean NOT NULL DEFAULT true,
  first_seen_at timestamptz NOT NULL DEFAULT now(),
  last_seen_at timestamptz NOT NULL DEFAULT now(),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE provider_catalog_snapshots (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  provider_id uuid NOT NULL REFERENCES providers(id),
  catalog_hash text NOT NULL,
  raw_payload jsonb NOT NULL,
  model_count integer NOT NULL,
  fetch_status text NOT NULL,
  fetched_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (provider_id, catalog_hash)
);

CREATE TABLE canonical_models (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  canonical_slug text UNIQUE NOT NULL,
  lab text,
  family text,
  version text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  discovered_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE provider_endpoints (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  provider_id uuid NOT NULL REFERENCES providers(id),
  provider_account_id uuid NOT NULL REFERENCES provider_accounts(id),
  provider_model_id text NOT NULL,
  model_type text NOT NULL DEFAULT 'chat',
  canonical_model_id uuid REFERENCES canonical_models(id),
  lifecycle_status text NOT NULL,
  access_status text NOT NULL,
  probe_status text NOT NULL DEFAULT 'not_run',
  capabilities jsonb NOT NULL DEFAULT '{}'::jsonb,
  metadata_hash text,
  -- Context-window / output eligibility (v3.8). effective_* are the values
  -- used by scoring/allocation; advertised/provider/probed are the inputs.
  advertised_context_window integer,
  provider_context_window integer,
  probed_context_window integer,
  effective_context_window integer,
  context_source text,
  context_confidence numeric(5,4),
  advertised_max_output_tokens integer,
  provider_max_output_tokens integer,
  probed_max_output_tokens integer,
  effective_max_output_tokens integer,
  first_seen_at timestamptz NOT NULL DEFAULT now(),
  last_seen_at timestamptz NOT NULL DEFAULT now(),
  removed_at timestamptz,
  UNIQUE (provider_id, provider_model_id, model_type)
);

CREATE TABLE endpoint_access_states (
  endpoint_id uuid PRIMARY KEY REFERENCES provider_endpoints(id),
  status text NOT NULL,
  reason_code text NOT NULL,
  effective_remaining jsonb,
  reset_at timestamptz,
  hard_stop_capable boolean NOT NULL,
  evidence jsonb NOT NULL,
  classified_at timestamptz NOT NULL DEFAULT now(),
  valid_until timestamptz
);

CREATE TABLE model_match_candidates (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  endpoint_id uuid NOT NULL REFERENCES provider_endpoints(id),
  canonical_model_id uuid REFERENCES canonical_models(id),
  method text NOT NULL,
  confidence numeric(5,4) NOT NULL,
  status text NOT NULL,
  evidence jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE endpoint_probes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  endpoint_id uuid NOT NULL REFERENCES provider_endpoints(id),
  suite_version text NOT NULL,
  probe_type text NOT NULL,
  request_hash text NOT NULL,
  passed boolean NOT NULL,
  http_status integer,
  normalized_error text,
  ttft_ms integer,
  total_latency_ms integer,
  input_tokens integer,
  output_tokens integer,
  details jsonb,
  started_at timestamptz NOT NULL,
  finished_at timestamptz NOT NULL
);

CREATE TABLE endpoint_health_observations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  endpoint_id uuid REFERENCES provider_endpoints(id),
  provider_id uuid REFERENCES providers(id),
  granularity text NOT NULL,
  status text NOT NULL,
  breaker_state text,
  success_rate numeric,
  error_rate numeric,
  latency_p50_ms integer,
  latency_p95_ms integer,
  latency_p99_ms integer,
  sample_count integer,
  window_start timestamptz,
  window_end timestamptz,
  observed_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE roles (
  id text PRIMARY KEY,
  requirements jsonb NOT NULL,
  expected_load jsonb NOT NULL,
  criticality integer NOT NULL,
  -- Optional single minimum quality gate per role (v3.10).
  minimum_quality_metric text,
  minimum_quality_value numeric,
  maximum_quality_metric text,
  maximum_quality_value numeric,
  quality_gate_index_version text,
  -- Dynamic role lifecycle (v3.19).
  role_lifecycle_status text NOT NULL DEFAULT 'active'
    CHECK (role_lifecycle_status IN (
      'discovered',
      'bootstrap_pending',
      'active',
      'needs_role_policy',
      'degraded_initial_capacity',
      'retiring',
      'retired',
      'retired_pending_delete'
    )),
  missing_since timestamptz,
  retired_at timestamptz,
  protected boolean NOT NULL DEFAULT false,
  role_template_name text,
  previous_role_name text,
  CONSTRAINT roles_minimum_quality_metric_check CHECK (
    minimum_quality_metric IS NULL
    OR minimum_quality_metric IN (
      'intelligence_index',
      'coding_index',
      'agentic_index'
    )
  ),
  CONSTRAINT roles_maximum_quality_metric_check CHECK (
    maximum_quality_metric IS NULL
    OR maximum_quality_metric IN (
      'intelligence_index',
      'coding_index',
      'agentic_index'
    )
  )
);

CREATE TABLE role_scores (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  role_id text NOT NULL REFERENCES roles(id),
  endpoint_id uuid NOT NULL REFERENCES provider_endpoints(id),
  score_version text NOT NULL,
  total_score numeric NOT NULL,
  component_scores jsonb NOT NULL,
  eligibility boolean NOT NULL,
  rejection_reasons jsonb,
  input_state_hash text NOT NULL,
  calculated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE allocation_plans (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  role_id text NOT NULL REFERENCES roles(id),
  status text NOT NULL,
  targets jsonb NOT NULL,
  constraint_report jsonb NOT NULL,
  input_state_hash text NOT NULL,
  quality_gate_report_json jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE combo_snapshots (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  role_id text NOT NULL REFERENCES roles(id),
  omniroute_combo_id text,
  state_hash text NOT NULL,
  state_json jsonb NOT NULL,
  phase text NOT NULL,
  run_id uuid REFERENCES sync_runs(id),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE published_generations (
  generation text NOT NULL,
  payload_hash text NOT NULL,
  payload_json jsonb NOT NULL,
  status text NOT NULL,
  acked_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (generation, payload_hash)
);

CREATE TABLE change_log (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id uuid REFERENCES sync_runs(id),
  entity_type text NOT NULL,
  entity_id text NOT NULL,
  action text NOT NULL,
  before_json jsonb,
  after_json jsonb,
  reason_codes jsonb,
  source_refs jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_provider_endpoints_status ON provider_endpoints(access_status, lifecycle_status);
CREATE INDEX idx_provider_endpoints_context ON provider_endpoints(effective_context_window);
CREATE INDEX idx_probes_endpoint_time ON endpoint_probes(endpoint_id, finished_at DESC);
CREATE INDEX idx_health_endpoint_time ON endpoint_health_observations(endpoint_id, observed_at DESC);
CREATE INDEX idx_role_scores_role_time ON role_scores(role_id, calculated_at DESC);
CREATE INDEX idx_provider_accounts_connection
  ON provider_accounts(provider_id, omniroute_connection_id);

CREATE TABLE global_allocation_plans (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  status text NOT NULL,
  quota_summary jsonb NOT NULL,
  oversubscription_report jsonb NOT NULL,
  input_state_hash text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE account_discovery_snapshots (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id uuid REFERENCES sync_runs(id),
  raw_provider_count integer NOT NULL,
  active_connection_count integer NOT NULL,
  virtual_account_count integer NOT NULL,
  independent_quota_pool_count integer NOT NULL,
  snapshot_json jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);


CREATE TABLE free_provider_registry_snapshots (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id uuid REFERENCES sync_runs(id),
  omniroute_version text,
  free_models_hash text,
  rankings_hashes jsonb,
  summary_hash text,
  raw_json jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- NOTE: across the free-registry and quota-attribution tables `provider_id`
-- holds the external OmniRoute provider slug (e.g. 'requesty', 'qiniu-ai'),
-- not the internal providers.id uuid. This is the natural key returned by
-- /api/free-models and models.dev (provider-keyed), so it is intentionally
-- a text key and not FK-bound to providers(id). Join via
-- providers.omniroute_provider_id when an internal row is needed.
CREATE TABLE free_provider_definitions (
  provider_id text PRIMARY KEY,
  free_category text NOT NULL,
  service_kinds jsonb NOT NULL DEFAULT '[]'::jsonb,
  has_free boolean NOT NULL,
  no_auth boolean NOT NULL,
  free_note text,
  source text NOT NULL,
  first_seen_at timestamptz NOT NULL DEFAULT now(),
  last_seen_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE free_model_definitions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  provider_id text NOT NULL,
  provider_model_id text NOT NULL,
  display_name text,
  free_type text NOT NULL,
  monthly_tokens numeric NOT NULL DEFAULT 0,
  credit_tokens numeric NOT NULL DEFAULT 0,
  omniroute_pool_key text,
  tos_verdict text,
  status text NOT NULL DEFAULT 'active',
  source_snapshot_id uuid REFERENCES free_provider_registry_snapshots(id),
  first_seen_at timestamptz NOT NULL DEFAULT now(),
  last_seen_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(provider_id, provider_model_id)
);

CREATE TABLE free_provider_quality_observations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  provider_id text NOT NULL,
  provider_model_id text,
  category text NOT NULL,
  normalized_score numeric,
  elo_raw numeric,
  confidence text,
  average_score numeric,
  model_count integer,
  observed_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_free_models_pool
  ON free_model_definitions(omniroute_pool_key, status);

CREATE INDEX idx_free_quality_provider_category
  ON free_provider_quality_observations(provider_id, category, observed_at DESC);


CREATE TABLE web_cookie_static_candidates (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  provider_account_id uuid NOT NULL REFERENCES provider_accounts(id),
  provider_model_id text NOT NULL,
  display_name text,
  capabilities jsonb NOT NULL DEFAULT '{}'::jsonb,
  session_status text NOT NULL,
  quota_status text,
  source text NOT NULL DEFAULT 'manual',
  primary_allowed boolean NOT NULL DEFAULT false,
  max_weight numeric NOT NULL DEFAULT 10,
  last_basic_probe_at timestamptz,
  last_success_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(provider_account_id, provider_model_id)
);


CREATE TABLE artificial_analysis_model_metrics (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  canonical_model_id uuid REFERENCES canonical_models(id),
  intelligence_index numeric,
  coding_index numeric,
  agentic_index numeric,
  median_output_tokens_per_second numeric,
  median_end_to_end_seconds numeric,
  index_version text,
  source_payload_hash text NOT NULL,
  fetched_at timestamptz NOT NULL DEFAULT now(),
  stale_after timestamptz NOT NULL,
  UNIQUE(canonical_model_id, source_payload_hash)
);

CREATE INDEX idx_aa_metrics_model_time
  ON artificial_analysis_model_metrics(canonical_model_id, fetched_at DESC);


CREATE TABLE artificial_analysis_index_migrations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  old_index_version text,
  new_index_version text NOT NULL,
  change_type text NOT NULL,
  status text NOT NULL,
  baseline_snapshot_json jsonb NOT NULL,
  distribution_report_json jsonb,
  threshold_proposal_json jsonb,
  validation_report_json jsonb,
  approved_by text,
  approved_at timestamptz,
  rolled_out_at timestamptz,
  rolled_back_at timestamptz,
  -- LLM-driven migration agent fields (v3.12-3.13).
  migration_model_endpoint_id uuid,
  migration_model_canonical_id uuid,
  migration_model_intelligence_index numeric,
  llm_prompt_hash text,
  llm_proposal_json jsonb,
  repair_attempts integer NOT NULL DEFAULT 0,
  dry_run_report_json jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE artificial_analysis_threshold_versions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  role_id text NOT NULL REFERENCES roles(id),
  metric text NOT NULL,
  threshold_value numeric NOT NULL,
  index_version text NOT NULL,
  percentile_at_creation numeric,
  migration_id uuid REFERENCES artificial_analysis_index_migrations(id),
  is_active boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(role_id, metric, index_version)
);

CREATE INDEX idx_aa_index_migrations_status
  ON artificial_analysis_index_migrations(status, created_at DESC);

CREATE INDEX idx_aa_threshold_versions_active
  ON artificial_analysis_threshold_versions(role_id, is_active);


-- Demand model has two complementary sources, not duplicates:
--  * role_consumers (+ hermes_inventory_runs), populated by the daily Hermes
--    inventory, is the authoritative consumer registry as of v3.19.
--  * agents / agent_role_usage_profiles / role_usage_dependencies cover agents
--    registered outside the Hermes inventory and observed runtime telemetry.
-- Forecasting prefers role_consumers when an entry exists, then falls back to
-- agent_role_usage_profiles, then to role_bootstrap_profiles.
CREATE TABLE agents (
  id text PRIMARY KEY,
  trigger_type text NOT NULL CHECK (
    trigger_type IN ('cron', 'interval', 'event', 'manual', 'continuous')
  ),
  schedule_expression text,
  timezone text,
  expected_runs_per_day numeric,
  p95_runs_per_day numeric,
  peak_concurrency integer NOT NULL DEFAULT 1,
  enabled boolean NOT NULL DEFAULT true,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE agent_role_usage_profiles (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_id text NOT NULL REFERENCES agents(id),
  role_id text NOT NULL REFERENCES roles(id),
  calls_per_agent_run numeric NOT NULL,
  average_input_tokens numeric,
  average_output_tokens numeric,
  p95_input_tokens numeric,
  p95_output_tokens numeric,
  peak_parallel_calls integer NOT NULL DEFAULT 1,
  source text NOT NULL CHECK (
    source IN ('observed', 'configured', 'bootstrap')
  ),
  confidence numeric(5,4) NOT NULL,
  valid_from timestamptz NOT NULL DEFAULT now(),
  valid_until timestamptz,
  UNIQUE(agent_id, role_id, valid_from)
);

CREATE TABLE role_usage_dependencies (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_kind text NOT NULL CHECK (
    source_kind IN ('all_agent_runs', 'agent_run', 'role_call', 'maintenance')
  ),
  source_id text NOT NULL,
  target_role_id text NOT NULL REFERENCES roles(id),
  calls_per_source_event numeric NOT NULL,
  average_input_tokens numeric,
  average_output_tokens numeric,
  enabled boolean NOT NULL DEFAULT true,
  valid_from timestamptz NOT NULL DEFAULT now(),
  valid_until timestamptz
);

CREATE TABLE agent_execution_observations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_id text NOT NULL REFERENCES agents(id),
  started_at timestamptz NOT NULL,
  finished_at timestamptz,
  status text NOT NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE role_usage_observations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_execution_id uuid REFERENCES agent_execution_observations(id),
  agent_id text REFERENCES agents(id),
  role_id text NOT NULL REFERENCES roles(id),
  request_count integer NOT NULL DEFAULT 1,
  input_tokens numeric,
  output_tokens numeric,
  peak_concurrency integer,
  observed_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE role_demand_forecasts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  role_id text NOT NULL REFERENCES roles(id),
  forecast_start timestamptz NOT NULL,
  forecast_end timestamptz NOT NULL,
  expected_requests numeric NOT NULL,
  protected_requests numeric NOT NULL,
  expected_input_tokens numeric,
  protected_input_tokens numeric,
  expected_output_tokens numeric,
  protected_output_tokens numeric,
  peak_concurrency integer,
  consumer_agents jsonb NOT NULL DEFAULT '[]'::jsonb,
  shared_dependency_breakdown jsonb NOT NULL DEFAULT '[]'::jsonb,
  source_mix jsonb NOT NULL DEFAULT '{}'::jsonb,
  confidence numeric(5,4) NOT NULL,
  input_state_hash text NOT NULL,
  -- Historical-reserve / cold-start blending (v3.16).
  demand_source text,
  base_historical_requests numeric,
  base_historical_input_tokens numeric,
  base_historical_output_tokens numeric,
  historical_reserve_multiplier numeric,
  cold_start_safety_multiplier numeric,
  bootstrap_weight numeric,
  history_weight numeric,
  representative_sample_count integer,
  representative_history_ready boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_agent_execution_observations_agent_time
  ON agent_execution_observations(agent_id, started_at DESC);

CREATE INDEX idx_role_usage_observations_role_time
  ON role_usage_observations(role_id, observed_at DESC);

CREATE INDEX idx_role_demand_forecasts_role_window
  ON role_demand_forecasts(role_id, forecast_start, forecast_end);

CREATE INDEX idx_role_usage_dependencies_target
  ON role_usage_dependencies(target_role_id, enabled);


CREATE TABLE role_bootstrap_profiles (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  role_id text NOT NULL REFERENCES roles(id),
  calls_per_run numeric NOT NULL,
  input_tokens_per_call numeric NOT NULL,
  output_tokens_per_call numeric NOT NULL,
  minimum_requests_per_day numeric,
  minimum_requests_per_week numeric,
  minimum_requests_per_month numeric,
  peak_parallel_calls integer NOT NULL DEFAULT 1,
  source text NOT NULL DEFAULT 'configured',
  active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_role_bootstrap_profiles_role_active
  ON role_bootstrap_profiles(role_id, active);


CREATE TABLE combo_review_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  review_model text,
  review_endpoint_id uuid REFERENCES provider_endpoints(id),
  prompt_hash text NOT NULL,
  input_plan_hash text NOT NULL,
  structured_review_json jsonb,
  accepted_diffs_json jsonb NOT NULL DEFAULT '[]'::jsonb,
  rejected_diffs_json jsonb NOT NULL DEFAULT '[]'::jsonb,
  final_combo_hash text,
  status text NOT NULL CHECK (
    status IN (
      'completed',
      'skipped_no_model',
      'failed',
      'no_valid_diffs'
    )
  ),
  created_at timestamptz NOT NULL DEFAULT now()
);


CREATE TABLE role_lifecycle_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  role_id text REFERENCES roles(id),
  role_name text NOT NULL,
  event_type text NOT NULL CHECK (event_type IN (
    'role_discovered',
    'role_activated',
    'role_marked_retiring',
    'role_retirement_cancelled',
    'role_retired',
    'role_combo_deleted',
    'role_policy_missing',
    'role_reference_detected',
    'role_rename_applied'
  )),
  details_json jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);


CREATE TABLE hermes_inventory_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_mode text NOT NULL CHECK (source_mode IN ('filesystem', 'command', 'http')),
  trigger_type text NOT NULL CHECK (trigger_type IN ('daily', 'manual', 'unknown_role')),
  source_hash text,
  roles_found integer NOT NULL DEFAULT 0,
  profiles_found integer NOT NULL DEFAULT 0,
  routines_found integer NOT NULL DEFAULT 0,
  status text NOT NULL CHECK (status IN ('running', 'completed', 'failed')),
  error_text text,
  started_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz
);

CREATE TABLE role_consumers (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  role_id text NOT NULL REFERENCES roles(id),
  -- Real Hermes consumer surfaces (the marketing umbrella "routine" = cron +
  -- webhook + api triggers): an interactive agent profile, a cron job, a webhook
  -- subscription (GitHub event or API trigger), an auxiliary model slot, or a
  -- long-running service.
  consumer_type text NOT NULL CHECK (
    consumer_type IN ('agent_profile', 'cron_job', 'webhook', 'service', 'auxiliary')
  ),
  consumer_key text NOT NULL,
  consumer_name text,
  trigger_type text NOT NULL CHECK (
    trigger_type IN ('cron', 'interval', 'event', 'manual', 'continuous')
  ),
  schedule_expression text,
  expected_runs_per_window numeric,
  calls_per_run numeric NOT NULL DEFAULT 1,
  average_input_tokens numeric,
  average_output_tokens numeric,
  peak_concurrency numeric,
  source_hash text,
  first_seen_at timestamptz NOT NULL DEFAULT now(),
  last_seen_at timestamptz NOT NULL DEFAULT now(),
  active boolean NOT NULL DEFAULT true,
  UNIQUE(role_id, consumer_type, consumer_key)
);

CREATE INDEX role_consumers_role_active_idx
  ON role_consumers(role_id, active);
