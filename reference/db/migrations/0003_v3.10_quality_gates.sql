-- v3.10 — single optional minimum quality gate per role.
ALTER TABLE roles
  ADD COLUMN IF NOT EXISTS minimum_quality_metric text,
  ADD COLUMN IF NOT EXISTS minimum_quality_value numeric,
  ADD COLUMN IF NOT EXISTS quality_gate_index_version text,
  ADD CONSTRAINT roles_minimum_quality_metric_check
    CHECK (
      minimum_quality_metric IS NULL
      OR minimum_quality_metric IN (
        'intelligence_index',
        'coding_index',
        'agentic_index'
      )
    );

ALTER TABLE allocation_plans
  ADD COLUMN IF NOT EXISTS quality_gate_report_json jsonb;
