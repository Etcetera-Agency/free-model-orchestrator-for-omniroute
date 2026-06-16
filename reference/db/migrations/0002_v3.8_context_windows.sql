-- v3.8 — context-window / max-output eligibility per provider endpoint.
ALTER TABLE provider_endpoints
  ADD COLUMN IF NOT EXISTS advertised_context_window integer,
  ADD COLUMN IF NOT EXISTS provider_context_window integer,
  ADD COLUMN IF NOT EXISTS probed_context_window integer,
  ADD COLUMN IF NOT EXISTS effective_context_window integer,
  ADD COLUMN IF NOT EXISTS context_source text,
  ADD COLUMN IF NOT EXISTS context_confidence numeric(5,4),
  ADD COLUMN IF NOT EXISTS advertised_max_output_tokens integer,
  ADD COLUMN IF NOT EXISTS provider_max_output_tokens integer,
  ADD COLUMN IF NOT EXISTS probed_max_output_tokens integer,
  ADD COLUMN IF NOT EXISTS effective_max_output_tokens integer;

CREATE INDEX IF NOT EXISTS idx_provider_endpoints_context
  ON provider_endpoints(effective_context_window);
