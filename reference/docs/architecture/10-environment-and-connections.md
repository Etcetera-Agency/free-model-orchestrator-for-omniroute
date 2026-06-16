
# Environment and External Connections

## Principles

Environment-specific locations and credentials are configured only through environment variables.

Repository configuration contains policies and defaults, not secrets.

## Required OmniRoute variables

```dotenv
OMNIROUTE_URL=http://127.0.0.1:20128
OMNIROUTE_API_KEY=
OMNIROUTE_REQUEST_TIMEOUT_MS=30000
```

`OMNIROUTE_URL` is the management/API base URL.

`OMNIROUTE_API_KEY` is required when OmniRoute authentication is enabled.

## Hermes adapter selection

```dotenv
HERMES_INVENTORY_MODE=filesystem
```

Allowed:

```text
filesystem
command
http
```

## Filesystem mode

```dotenv
HERMES_HOME=/home/hermes/.hermes
HERMES_AGENTS_PATH=/path/to/hermes/agents
HERMES_ROUTINES_PATH=/path/to/hermes/routines
HERMES_CRON_JOBS_PATH=/home/hermes/.hermes/cron/jobs.json
HERMES_STATE_DB_PATH=/home/hermes/.hermes/state.db
```

Defaults derived from `HERMES_HOME`:

```text
HERMES_CRON_JOBS_PATH = ${HERMES_HOME}/cron/jobs.json
HERMES_STATE_DB_PATH = ${HERMES_HOME}/state.db
```

Agent/routine paths must be explicit unless the installed Hermes layout is known and version-pinned.

## Command mode

```dotenv
HERMES_INVENTORY_COMMAND=hermes inventory --format json
HERMES_INVENTORY_COMMAND_TIMEOUT_MS=60000
```

The command must output normalized JSON to stdout.

## HTTP mode

```dotenv
HERMES_INVENTORY_URL=http://127.0.0.1:9000/inventory
HERMES_INVENTORY_TOKEN=
HERMES_INVENTORY_TIMEOUT_MS=30000
```

## Inventory schedule

```dotenv
HERMES_INVENTORY_CRON=0 4 * * *
HERMES_INVENTORY_TIMEZONE=Europe/Bucharest
HERMES_UNKNOWN_ROLE_TRIGGER=true
```

The daily inventory is mandatory.

Unknown-role detection may trigger an additional immediate inventory.

## Database

```dotenv
DATABASE_URL=postgresql://user:password@postgres:5432/free_model_orchestrator
```

## Artificial Analysis

```dotenv
ARTIFICIAL_ANALYSIS_API_KEY=
ARTIFICIAL_ANALYSIS_BASE_URL=https://artificialanalysis.ai
```

## Runtime

```dotenv
LOG_LEVEL=info
ENVIRONMENT=production
```

## Startup validation

At startup:

```text
validate OMNIROUTE_URL
validate DATABASE_URL
validate HERMES_INVENTORY_MODE
validate mode-specific Hermes variables
validate writable/readable paths where applicable
validate inventory cron expression
test OmniRoute management connectivity
test database connectivity
```

Do not test model endpoints during startup.

## Secret handling

Never include in Inspector/reviewer prompts:

```text
OMNIROUTE_API_KEY
HERMES_INVENTORY_TOKEN
DATABASE_URL credentials
provider credentials
cookies
credential fingerprints
```

Prompts may include only sanitized endpoint/account IDs and derived metadata.
