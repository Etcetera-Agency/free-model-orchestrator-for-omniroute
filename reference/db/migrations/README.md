# Database migrations

Policy:

- **Fresh install** → run `db/schema.sql` once. It already contains the full
  current-state schema (v3.19) with every column folded into its `CREATE TABLE`.
- **Existing database** created by an older version → apply the numbered scripts
  here in order. Every statement is idempotent (`ADD COLUMN IF NOT EXISTS`,
  `CREATE TABLE IF NOT EXISTS`), so re-running is safe and a script that a
  database already satisfies is a no-op.

Each file corresponds to the schema delta that a feature version introduced.
These are the same `ALTER`/`CREATE` statements that previously lived inline at
the end of `schema.sql`; they were extracted so the baseline stays clean.

| File | Version | Adds |
| --- | --- | --- |
| `0001_v3.4_account_quota_scope.sql` | 3.4 | `provider_accounts` quota-scope identity columns |
| `0002_v3.8_context_windows.sql` | 3.8 | `provider_endpoints` context/output columns + index |
| `0003_v3.10_quality_gates.sql` | 3.10 | `roles` quality-gate columns; `allocation_plans.quality_gate_report_json` |
| `0004_v3.13_index_migration_llm.sql` | 3.12–3.13 | `artificial_analysis_index_migrations` LLM-agent columns |
| `0005_v3.15_quota_attribution.sql` | 3.15 | `role_demand_forecasts` quota-attribution linkage |
| `0006_v3.16_cold_start_demand.sql` | 3.16 | `role_demand_forecasts` historical-reserve / cold-start columns |
| `0007_v3.19_role_lifecycle.sql` | 3.19 | `roles` lifecycle columns |
| `0008_v3.20_atomic_run_locks.sql` | 3.20 | partial unique index for active `sync_runs` lock rows |
| `0009_v3.21_quality_band_upper_bound.sql` | 3.21 | `roles.maximum_quality_*` quality-band columns |
| `0010_v3.22_auxiliary_role_consumers.sql` | 3.22 | `role_consumers.consumer_type` accepts Hermes auxiliary slots |
| `0011_v3.23_provider_endpoint_identity.sql` | 3.23 | `provider_endpoints.provider_id` and provider/model dedupe identity |
| `0012_v3.24_drop_endpoint_account_identity.sql` | 3.24 | drop redundant account-level `provider_endpoints` unique constraint |
| `0013_v3.25_published_generations.sql` | 3.25 | `published_generations` payload-hash publish records |

> The AA index-migration / threshold-version tables, demand tables, quota
> attribution tables, bootstrap profiles, combo review, role lifecycle events,
> Hermes inventory and role consumers were introduced as whole new tables in
> their respective versions. On an existing DB they are created by re-running
> `schema.sql` (all `CREATE TABLE` there are plain creates; wrap in a
> transaction and ignore "already exists" for tables you have), or you can lift
> the relevant `CREATE TABLE` block. Only column additions to pre-existing
> tables need the scripts above.
