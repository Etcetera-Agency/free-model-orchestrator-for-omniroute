ALTER TABLE endpoint_access_states
  DROP CONSTRAINT IF EXISTS endpoint_access_states_quota_rule_id_fkey,
  DROP COLUMN IF EXISTS quota_rule_id;

ALTER TABLE provider_accounts
  DROP CONSTRAINT IF EXISTS provider_accounts_quota_pool_id_fkey,
  DROP COLUMN IF EXISTS quota_pool_id;

ALTER TABLE role_demand_forecasts
  DROP CONSTRAINT IF EXISTS role_demand_forecasts_quota_pool_id_fkey,
  DROP CONSTRAINT IF EXISTS role_demand_forecasts_quota_attribution_group_id_fkey,
  DROP COLUMN IF EXISTS quota_pool_id,
  DROP COLUMN IF EXISTS quota_attribution_group_id,
  DROP COLUMN IF EXISTS quota_attribution_status;

DROP TABLE IF EXISTS quota_attribution_events;
DROP TABLE IF EXISTS endpoint_quota_attribution;
DROP TABLE IF EXISTS quota_attribution_groups;
DROP TABLE IF EXISTS role_quota_budgets;
DROP TABLE IF EXISTS quota_pool_members;
DROP TABLE IF EXISTS quota_reservations;
DROP TABLE IF EXISTS quota_observations;
DROP TABLE IF EXISTS quota_rules;
DROP TABLE IF EXISTS quota_source_snapshots;
DROP TABLE IF EXISTS quota_pools;
