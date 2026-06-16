-- v3.4 — quota-scope identity on provider accounts.
ALTER TABLE provider_accounts
  ADD COLUMN IF NOT EXISTS quota_scope_type text,
  ADD COLUMN IF NOT EXISTS quota_scope_key text,
  ADD COLUMN IF NOT EXISTS provider_instance_key text;
