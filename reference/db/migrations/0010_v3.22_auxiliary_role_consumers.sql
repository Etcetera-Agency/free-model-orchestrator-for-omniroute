-- v3.22 — allow Hermes auxiliary model slots as role consumers.
ALTER TABLE role_consumers
  DROP CONSTRAINT IF EXISTS role_consumers_consumer_type_check;

ALTER TABLE role_consumers
  ADD CONSTRAINT role_consumers_consumer_type_check CHECK (
    consumer_type IN ('agent_profile', 'cron_job', 'webhook', 'service', 'auxiliary')
  );
