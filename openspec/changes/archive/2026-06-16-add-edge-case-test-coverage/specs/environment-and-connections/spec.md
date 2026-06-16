# environment-and-connections Specification

## MODIFIED Requirements

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
