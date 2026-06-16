# environment-and-connections Specification

## Purpose
TBD - created by archiving change add-foundation. Update Purpose after archive.
## Requirements
### Requirement: Secrets only via environment

The system SHALL read environment-specific locations and credentials only from
environment variables; repository configuration SHALL contain policies and
defaults, never secrets.

#### Scenario: Secret in repo config
- GIVEN a credential is needed (OmniRoute key, DB password, Hermes token)
- WHEN configuration is loaded
- THEN the value comes from an environment variable, not a committed file

### Requirement: Startup validation

The system SHALL validate all required startup settings before contacting
providers. Invalid OmniRoute URL scheme, empty OmniRoute URL, missing database
URL, invalid Hermes inventory mode, malformed cron, missing filesystem paths,
missing command, malformed HTTP inventory URL, and non-dict health-check payloads
SHALL fail fast.

#### Scenario: Bad OmniRoute URL
- GIVEN `omniroute_url` is empty or uses an unsupported scheme
- WHEN config validation runs
- THEN validation raises `ValueError`

#### Scenario: Missing database URL
- GIVEN `database_url` is absent
- WHEN config validation runs
- THEN validation raises `ValueError`

#### Scenario: Invalid inventory mode
- GIVEN `hermes_inventory_mode` is not supported
- WHEN config validation runs
- THEN validation raises `ValueError`

#### Scenario: Bad inventory cron
- GIVEN `hermes_inventory_cron` does not contain exactly five non-empty fields
- WHEN config validation runs
- THEN validation raises `ValueError`

#### Scenario: Missing filesystem inventory path
- GIVEN filesystem inventory mode is selected
- WHEN any required filesystem path is missing
- THEN validation raises `ValueError`

#### Scenario: Missing command inventory command
- GIVEN command inventory mode is selected without `hermes_inventory_command`
- WHEN config validation runs
- THEN validation raises `ValueError`

#### Scenario: Bad HTTP inventory URL
- GIVEN HTTP inventory mode is selected with an empty or malformed URL
- WHEN config validation runs
- THEN validation raises `ValueError`

#### Scenario: Health check payload is not an object
- GIVEN `health_check()` returns a non-dict payload
- WHEN startup validation checks health
- THEN validation raises `ValueError`
### Requirement: Prompt secret redaction

The system SHALL never include `OMNIROUTE_API_KEY`, `HERMES_INVENTORY_TOKEN`,
database credentials, provider credentials, cookies, or credential fingerprints
in any Inspector or reviewer prompt; prompts may include only sanitized
endpoint/account ids and derived metadata.

#### Scenario: Building an LLM prompt
- GIVEN an Inspector or reviewer prompt is assembled
- WHEN it includes endpoint context
- THEN no secret material is present, only sanitized identifiers

