# environment-and-connections Specification

## ADDED Requirements

### Requirement: Secrets only via environment

The system SHALL read environment-specific locations and credentials only from
environment variables; repository configuration SHALL contain policies and
defaults, never secrets.

#### Scenario: Secret in repo config
- GIVEN a credential is needed (OmniRoute key, DB password, Hermes token)
- WHEN configuration is loaded
- THEN the value comes from an environment variable, not a committed file

### Requirement: Startup validation

The system SHALL validate `OMNIROUTE_URL`, `DATABASE_URL`, the Hermes inventory
mode and mode-specific variables, the inventory cron expression, and test
OmniRoute management and database connectivity at startup. The system SHALL NOT
test model endpoints during startup.

#### Scenario: Bad cron at startup
- GIVEN an invalid `HERMES_INVENTORY_CRON`
- WHEN the service starts
- THEN startup validation fails before any run

#### Scenario: No model probing at startup
- GIVEN startup validation runs
- WHEN connectivity checks execute
- THEN model endpoints are not called

### Requirement: Prompt secret redaction

The system SHALL never include `OMNIROUTE_API_KEY`, `HERMES_INVENTORY_TOKEN`,
database credentials, provider credentials, cookies, or credential fingerprints
in any Inspector or reviewer prompt; prompts may include only sanitized
endpoint/account ids and derived metadata.

#### Scenario: Building an LLM prompt
- GIVEN an Inspector or reviewer prompt is assembled
- WHEN it includes endpoint context
- THEN no secret material is present, only sanitized identifiers
