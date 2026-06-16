-- v3.15 — link demand forecasts to quota attribution groups.
ALTER TABLE role_demand_forecasts
  ADD COLUMN IF NOT EXISTS quota_attribution_group_id uuid
    REFERENCES quota_attribution_groups(id),
  ADD COLUMN IF NOT EXISTS quota_attribution_status text;
