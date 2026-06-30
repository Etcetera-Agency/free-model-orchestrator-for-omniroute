-- v3.23 - provider/model endpoints overwrite instead of duplicating across account rows.
ALTER TABLE provider_endpoints
  ADD COLUMN IF NOT EXISTS provider_id uuid REFERENCES providers(id);

UPDATE provider_endpoints pe
SET provider_id = pa.provider_id
FROM provider_accounts pa
WHERE pe.provider_account_id = pa.id
  AND pe.provider_id IS NULL;

CREATE TEMP TABLE endpoint_dedup_map ON COMMIT DROP AS
WITH ranked AS (
  SELECT
    pe.id AS endpoint_id,
    first_value(pe.id) OVER (
      PARTITION BY pe.provider_id, pe.provider_model_id, pe.model_type
      ORDER BY
        CASE WHEN pe.lifecycle_status = 'active' THEN 0 ELSE 1 END,
        CASE WHEN pe.access_status = 'confirmed' THEN 0 ELSE 1 END,
        CASE WHEN pe.probe_status = 'passed' THEN 0 ELSE 1 END,
        CASE WHEN pe.canonical_model_id IS NOT NULL THEN 0 ELSE 1 END,
        pe.last_seen_at DESC,
        pe.first_seen_at ASC,
        pe.id
    ) AS keeper_id
  FROM provider_endpoints pe
  WHERE pe.provider_id IS NOT NULL
)
SELECT endpoint_id AS duplicate_id, keeper_id
FROM ranked
WHERE endpoint_id <> keeper_id;

UPDATE quota_reservations qr
SET endpoint_id = m.keeper_id
FROM endpoint_dedup_map m
WHERE qr.endpoint_id = m.duplicate_id;

DELETE FROM endpoint_access_states eas
USING endpoint_dedup_map m
WHERE eas.endpoint_id = m.duplicate_id
  AND EXISTS (
    SELECT 1
    FROM endpoint_access_states keeper
    WHERE keeper.endpoint_id = m.keeper_id
  );

UPDATE endpoint_access_states eas
SET endpoint_id = m.keeper_id
FROM endpoint_dedup_map m
WHERE eas.endpoint_id = m.duplicate_id;

UPDATE model_match_candidates mmc
SET endpoint_id = m.keeper_id
FROM endpoint_dedup_map m
WHERE mmc.endpoint_id = m.duplicate_id;

UPDATE endpoint_probes ep
SET endpoint_id = m.keeper_id
FROM endpoint_dedup_map m
WHERE ep.endpoint_id = m.duplicate_id;

UPDATE endpoint_health_observations eho
SET endpoint_id = m.keeper_id
FROM endpoint_dedup_map m
WHERE eho.endpoint_id = m.duplicate_id;

UPDATE role_scores rs
SET endpoint_id = m.keeper_id
FROM endpoint_dedup_map m
WHERE rs.endpoint_id = m.duplicate_id;

DELETE FROM endpoint_quota_attribution eqa
USING endpoint_dedup_map m
WHERE eqa.endpoint_id = m.duplicate_id
  AND EXISTS (
    SELECT 1
    FROM endpoint_quota_attribution keeper
    WHERE keeper.endpoint_id = m.keeper_id
      AND keeper.account_or_connection_id IS NOT DISTINCT FROM eqa.account_or_connection_id
      AND keeper.valid_from = eqa.valid_from
  );

UPDATE endpoint_quota_attribution eqa
SET endpoint_id = m.keeper_id
FROM endpoint_dedup_map m
WHERE eqa.endpoint_id = m.duplicate_id;

UPDATE combo_review_runs crr
SET review_endpoint_id = m.keeper_id
FROM endpoint_dedup_map m
WHERE crr.review_endpoint_id = m.duplicate_id;

DELETE FROM provider_endpoints pe
USING endpoint_dedup_map m
WHERE pe.id = m.duplicate_id;

ALTER TABLE provider_endpoints
  ALTER COLUMN provider_id SET NOT NULL;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'provider_endpoints_provider_model_identity_key'
  ) THEN
    ALTER TABLE provider_endpoints
      ADD CONSTRAINT provider_endpoints_provider_model_identity_key
      UNIQUE (provider_id, provider_model_id, model_type);
  END IF;
END $$;
