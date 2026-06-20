# wire-account-discovery-stage

## Why

The `account-discovery` capability (`src/fmo/accounts.py`:
`discover_live_accounts`, `group_quota_pools`, `usable_capacity`, shared-pool /
independence detection) is fully implemented and unit-tested, but it is imported
**only by tests** — never by the production composition. Two problems follow:

1. The CLI command `discover-accounts` does not run account discovery. In
   `composition.py::_COMMAND_STAGE_NAMES` all three of `sync-free-registry`,
   `discover-accounts`, and `scan-providers` map to the single
   `free-candidate-discovery` stage, and that stage runs registry sync +
   catalog scan (`_free_candidate_stage`), not connection/rate-limit fetch and
   quota-pool grouping. So `discover-accounts` silently runs a catalog scan.
2. Quota-pool independence (`confirmed | inferred | assumed_shared | unknown`)
   from connections + rate-limit availability is never computed in the daily
   `full` run. The core invariant "multiple accounts of one provider are NOT
   independent capacity unless `confirmed`" depends on this grouping, so
   allocation can over-count shared capacity.

The `account-discovery` spec already requires a live OmniRoute connection/account
fetch before grouping; it just isn't wired into the runnable pipeline.

## What Changes

- Add a dedicated `account-discovery` pipeline stage that runs
  `discover_live_accounts` against the OmniRoute management API, groups quota
  pools, and persists pool membership / independence status through the
  repository.
- Place the stage in the canonical pipeline before quota-sync/scoring so
  allocation consumes confirmed-independence capacity (after candidate
  discovery, alongside the existing connection-derived inputs).
- Map the CLI `discover-accounts` command to the new stage (not to
  `free-candidate-discovery`), so `discover-accounts` runs account discovery and
  returns that stage's real outcome.
- Keep conservative fallback: when the rate-limit fetch is unavailable, group
  pools conservatively and do not promote any connection to `confirmed`.

## Impact

- Modified specs: `pipeline-orchestration` (ordered run + a new "account
  discovery produces real effects" requirement), `cli-and-operations`
  (`discover-accounts` dispatches to the account-discovery stage).
- Affected code: `src/fmo/composition.py` (`_COMMAND_STAGE_NAMES`,
  `build_canonical_stages`, `CANONICAL_STAGE_NAMES`), `src/fmo/pipeline.py`
  (stage name list), new adapter in `src/fmo/composition_stages.py` driving
  `src/fmo/accounts.py`.
- Depends on: `account-discovery` spec (live fetch already specified).
- Feeds: quota-manager safety gates, allocation oversubscription gate.
