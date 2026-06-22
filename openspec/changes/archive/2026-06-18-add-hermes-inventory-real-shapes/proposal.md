# Change: Hermes inventory ingestion from real Hermes source shapes

## Why

The TODO defers realistic Hermes inventory ingestion. The previous parser
consumed a fabricated `{"roles": [...]}` payload that does not match any real
Hermes artifact. The authoritative shapes live in `NousResearch/hermes-agent`
(tag `v2026.6.19`).

## What Changes

- Hermes inventory reads the **real Hermes source shapes** instead of a
  fabricated intermediate:
  - `~/.hermes/cron/jobs.json` jobs (`cron/jobs.py`); cadence from the job
    `schedule` object; routed role from the job `model`, which is the OmniRoute
    **combo** the routine targets (one combo per role).
  - `~/.hermes/webhook_subscriptions.json` routes (`hermes_cli/webhook.py`);
    event-driven cadence.
  - `hermes profile list` records (`hermes_cli/profiles.py`); a running gateway
    is a `service`, otherwise an `agent_profile`.
  - observed `calls_per_run` from the `~/.hermes/state.db` `sessions` table
    (`hermes_state.py`), grouped by the combo in `sessions.model`.

## Impact

- Affected specs: `hermes-inventory`
- Affected code: `src/fmo/hermes_inventory.py`
- Fixtures: `reference/fixtures/hermes/*` (cron jobs, webhook subscriptions,
  profiles, `state.db` schema + sessions)
- Tests: `tests/test_hermes_inventory_real_shapes.py`
