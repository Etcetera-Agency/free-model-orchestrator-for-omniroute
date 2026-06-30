-- v3.24 - drop the dead account-level endpoint identity constraint.
--
-- v3.23 moved endpoint identity to (provider_id, provider_model_id, model_type)
-- and made the provider-level unique the upsert arbiter. The original
-- (provider_account_id, provider_model_id, model_type) unique is now redundant
-- (the provider-level unique already permits at most one row per provider/model,
-- so per-account uniqueness is implied) and only adds a second ON CONFLICT
-- arbiter that could surprise the repository upsert. Drop it.
--
-- The constraint was created inline in schema.sql, so on an existing database it
-- carries a Postgres auto-generated name. Resolve it by its exact column set
-- rather than by a literal name, and never the v3.23 provider-level constraint.
DO $$
DECLARE
  target_conname text;
BEGIN
  SELECT con.conname
  INTO target_conname
  FROM pg_constraint con
  JOIN pg_class rel ON rel.oid = con.conrelid
  WHERE rel.relname = 'provider_endpoints'
    AND con.contype = 'u'
    AND (
      SELECT array_agg(att.attname ORDER BY att.attname)
      FROM unnest(con.conkey) AS k(attnum)
      JOIN pg_attribute att
        ON att.attrelid = con.conrelid
       AND att.attnum = k.attnum
    ) = ARRAY['model_type', 'provider_account_id', 'provider_model_id']
  LIMIT 1;

  IF target_conname IS NOT NULL THEN
    EXECUTE format('ALTER TABLE provider_endpoints DROP CONSTRAINT %I', target_conname);
  END IF;
END $$;
