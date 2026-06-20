-- v3.20 — atomic active run-lock acquisition.
CREATE UNIQUE INDEX IF NOT EXISTS sync_runs_active_lock_name_idx
  ON sync_runs (trigger)
  WHERE run_type = 'lock'
    AND status = 'held'
    AND finished_at IS NULL;
