## ADDED Requirements

### Requirement: Hermes command/http adapters and live enumeration

The system SHALL provide command and http Hermes inventory adapters that return
the same real source shapes as the filesystem reader and raise structured errors
on failure. Profiles SHALL be enumerated live by scanning the real profile
directories and reading each profile's `config.yaml` model (the OmniRoute combo),
instead of relying on a caller-supplied profile listing. `service` consumers SHALL
be derived from the enabled Hermes gateway platforms configuration.

#### Scenario: Command adapter returns real shapes
- GIVEN the command inventory adapter is configured
- WHEN it runs
- THEN it returns the real cron/webhook/profile/session shapes
- AND a command failure raises a structured error

#### Scenario: Live profile enumeration
- GIVEN real profile directories exist with `config.yaml` model values
- WHEN the inventory enumerates profiles
- THEN each profile is discovered by scanning the directories
- AND its routed role comes from the profile's configured combo

#### Scenario: Service from gateway config
- GIVEN the Hermes gateway platforms configuration enables a long-running platform
- WHEN the inventory runs
- THEN a `service` consumer is recorded for it
