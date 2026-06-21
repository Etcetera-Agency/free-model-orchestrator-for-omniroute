-- v3.21 — optional upper quality band per role.
ALTER TABLE roles
  ADD COLUMN IF NOT EXISTS maximum_quality_metric text,
  ADD COLUMN IF NOT EXISTS maximum_quality_value numeric;

DO $$
BEGIN
  ALTER TABLE roles
    ADD CONSTRAINT roles_maximum_quality_metric_check
    CHECK (
      maximum_quality_metric IS NULL
      OR maximum_quality_metric IN (
        'intelligence_index',
        'coding_index',
        'agentic_index'
      )
    );
EXCEPTION
  WHEN duplicate_object THEN NULL;
END $$;
