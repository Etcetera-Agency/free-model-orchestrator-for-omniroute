-- v3.16 — historical-reserve and cold-start blending on demand forecasts.
ALTER TABLE role_demand_forecasts
  ADD COLUMN IF NOT EXISTS demand_source text,
  ADD COLUMN IF NOT EXISTS base_historical_requests numeric,
  ADD COLUMN IF NOT EXISTS base_historical_input_tokens numeric,
  ADD COLUMN IF NOT EXISTS base_historical_output_tokens numeric,
  ADD COLUMN IF NOT EXISTS historical_reserve_multiplier numeric,
  ADD COLUMN IF NOT EXISTS cold_start_safety_multiplier numeric,
  ADD COLUMN IF NOT EXISTS bootstrap_weight numeric,
  ADD COLUMN IF NOT EXISTS history_weight numeric,
  ADD COLUMN IF NOT EXISTS representative_sample_count integer,
  ADD COLUMN IF NOT EXISTS representative_history_ready boolean
    NOT NULL DEFAULT false;
