-- Free Model Orchestrator -- consolidated current-state schema (v3.28).
--
-- Fresh installs create only the publisher-side runtime state FMO still owns:
-- runs/locks, Hermes role inventory, demand forecasts, audit, and published
-- pool generations. Provider/model/endpoint/probe/scoring/allocation tables
-- are owned outside FMO or removed.

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

CREATE TABLE roles (
  id text PRIMARY KEY,
  requirements jsonb NOT NULL,
  expected_load jsonb NOT NULL,
  criticality integer NOT NULL,
  minimum_quality_metric text,
  minimum_quality_value numeric,
  maximum_quality_metric text,
  maximum_quality_value numeric,
  quality_gate_index_version text,
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

CREATE INDEX idx_role_demand_forecasts_role_window
  ON role_demand_forecasts(role_id, forecast_start, forecast_end);

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
