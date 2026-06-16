-- v3.12-3.13 — LLM-driven AA index migration agent fields.
ALTER TABLE artificial_analysis_index_migrations
  ADD COLUMN IF NOT EXISTS migration_model_endpoint_id uuid,
  ADD COLUMN IF NOT EXISTS migration_model_canonical_id uuid,
  ADD COLUMN IF NOT EXISTS migration_model_intelligence_index numeric,
  ADD COLUMN IF NOT EXISTS llm_prompt_hash text,
  ADD COLUMN IF NOT EXISTS llm_proposal_json jsonb,
  ADD COLUMN IF NOT EXISTS repair_attempts integer NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS dry_run_report_json jsonb;
