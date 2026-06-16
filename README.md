# Free Model Orchestrator for OmniRoute

Free Model Orchestrator keeps OmniRoute role combos filled with endpoints that
can be used without paid spend. It discovers free candidates, validates quota
safety, probes only confirmed-free capacity, scores usable endpoints, allocates
role combos, and applies minimal diffs to OmniRoute.

Main invariant:

```text
No probe or production request may exceed confirmed free capacity.
```

If free access, hard-stop quota behavior, session health, probe result, or role
capability support cannot be confirmed, the endpoint is excluded or degraded
instead of used.

## Current Scope

Implemented package modules live under `src/fmo/`:

- OmniRoute client, startup config validation, DB migrations, idempotency, state guards.
- Provider/account discovery, catalog snapshots, free candidate detection, model matching.
- Quota research, access classification, quota attribution, quota manager safety gates.
- Probe runner, telemetry normalization, quality gates, context-window eligibility.
- Demand forecasting, global allocation, combo applier, audit, rollback.
- Hermes inventory and dynamic role lifecycle.
- Advisory smart combo review, Artificial Analysis index migration, LLM prompt safety.
- Web-cookie candidate handling and CLI command surface.

OpenSpec living specs are in `openspec/specs/`. Historical/implementation changes
are in `openspec/changes/`.

## Repo Layout

```text
src/fmo/                 Python package
tests/                   pytest regression and simulated E2E tests
reference/               source ТЗ, DB schema, migration notes
reference/db/schema.sql  PostgreSQL schema used by tests and migrations
openspec/                specs, proposals, task lists, archive
pyproject.toml           package metadata, test config, CLI entrypoint
```

## Requirements

- Python 3.12+
- PostgreSQL binaries for tests that use a real ephemeral local Postgres
- Node.js only for OpenSpec CLI validation

Use isolated installs only. Do not install dependencies globally from this repo.

## Setup

```bash
cd free-model-orchestrator-for-omniroute

python3 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
```

The test suite fixture starts an isolated temporary PostgreSQL instance using
local `initdb`, `postgres`, and `createdb` binaries. No shared database is
required for tests.

## Configuration

Startup validation expects:

- `OMNIROUTE_URL`: `http` or `https` URL.
- `DATABASE_URL`: PostgreSQL connection URL.
- `HERMES_INVENTORY_MODE`: `filesystem`, `command`, or `http`.
- `HERMES_INVENTORY_CRON`: five non-empty cron fields.

Mode-specific fields:

- `filesystem`: `HERMES_HOME`, `HERMES_AGENTS_PATH`, `HERMES_ROUTINES_PATH`.
- `command`: `HERMES_INVENTORY_COMMAND`.
- `http`: `HERMES_INVENTORY_URL` with `http` or `https` scheme and host.

PostgreSQL can be any reachable instance via `DATABASE_URL`. Tests do not need
that setting because they create their own temporary database.

## CLI

Package entrypoint:

```bash
.venv/bin/free-model-orchestrator --help
```

Available commands:

```text
sync-free-registry
discover-accounts
scan-providers
research-quotas
classify-access
sync-metadata
match-models
probe-models
sync-telemetry
sync-quotas
score-roles
allocate
diff
apply
rollback
full
explain-endpoint
explain-role
aa-index status|analyze|proposal|approve|reject|rollout|rollback
```

Common flags:

```text
--dry-run --provider --account --endpoint --role --run-id --force --json --verbose
```

Exit codes:

```text
0 success
2 partial_stale
3 validation_failed
4 external_dependency_failed
5 unsafe_to_apply
6 apply_failed_rolled_back
7 rollback_failed
```

## Testing

Run full suite:

```bash
.venv/bin/python -m pytest -q
```

Run a targeted file:

```bash
.venv/bin/python -m pytest tests/test_allocation.py -q
```

Validate OpenSpec:

```bash
openspec validate --all --strict
```

Current expected validation after the edge-case coverage slice:

```text
144 passed
31 OpenSpec items passed
```

## Safety Model

The orchestrator fails closed:

- Unknown or stale evidence does not become free access.
- Paid charge evidence and manual denial override zero-price signals.
- Free quota is usable only with confirmed hard-stop behavior, limit, remaining,
  reset time, and remaining quota above safety buffer.
- Probe runs only for confirmed-free endpoints with reserved capacity.
- Apply is guarded by DB availability, saved snapshot, valid desired state,
  quota safety, and passing smoke/probe checks.
- Web-cookie endpoints are never auto-discovered and remain fallback-oriented
  unless explicitly configured and capability-confirmed.

## Development Flow

OpenSpec workflow:

```text
proposal + tasks
→ failing tests
→ minimal implementation fixes
→ targeted pytest
→ full pytest
→ openspec validate --all --strict
→ archive when approved
```

When production code changes expose follow-up work, record it in
`openspec/TODO.md` before finishing the OpenSpec task.

## Reference

The original Russian technical brief is preserved in `reference/README.md`.
Database schema is in `reference/db/schema.sql`.
