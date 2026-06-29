-- v3.25 - record idempotent fmo-pools/v1 publish attempts.
CREATE TABLE IF NOT EXISTS published_generations (
  generation text NOT NULL,
  payload_hash text NOT NULL,
  payload_json jsonb NOT NULL,
  status text NOT NULL,
  acked_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (generation, payload_hash)
);
