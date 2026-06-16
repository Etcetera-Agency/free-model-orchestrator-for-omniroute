-- v3.19 — dynamic role lifecycle columns.
ALTER TABLE roles
  ADD COLUMN IF NOT EXISTS role_lifecycle_status text NOT NULL DEFAULT 'active'
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
  ADD COLUMN IF NOT EXISTS missing_since timestamptz,
  ADD COLUMN IF NOT EXISTS retired_at timestamptz,
  ADD COLUMN IF NOT EXISTS protected boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS role_template_name text,
  ADD COLUMN IF NOT EXISTS previous_role_name text;
