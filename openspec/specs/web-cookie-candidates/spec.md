# web-cookie-candidates Specification

## Purpose
TBD - created by archiving change add-web-cookie-and-cli. Update Purpose after archive.
## Requirements
### Requirement: No automatic discovery

The system SHALL consider web-cookie endpoints only when explicitly configured
and SHALL filter out connection-sourced candidates whose `auth_type` is not
`web_cookie`.

#### Scenario: Non-web-cookie connection source
- GIVEN a candidate comes from connections with `auth_type` other than `web_cookie`
- WHEN web-cookie candidates are loaded
- THEN the candidate is filtered out
### Requirement: Capability-gated role eligibility

The system SHALL allow a web-cookie endpoint for a role only when the role is
fallback-eligible and all required capabilities are explicitly true. Missing or
false capability flags SHALL make the endpoint ineligible.

#### Scenario: Capability false or missing
- GIVEN a web-cookie endpoint has a false or missing required capability
- WHEN role eligibility is checked
- THEN it is not eligible
### Requirement: Probe and session health

The system SHALL run text probes and session health checks before considering a
web-cookie endpoint. Login pages, challenge pages, HTML shell responses, empty
responses, and whitespace-only responses SHALL fail text probe. Challenge pages
SHALL fail session health.

#### Scenario: Text probe bad response
- GIVEN probe output is login, challenge, raw HTML, empty or whitespace-only
- WHEN web-cookie text probe runs
- THEN it fails

#### Scenario: Session challenge
- GIVEN session health response indicates a challenge
- WHEN session health is checked
- THEN the session is unhealthy
### Requirement: Fallback-only with limited weight

The system SHALL treat a web-cookie endpoint as fallback-only (not primary
without explicit override) and SHALL NOT count unknown quota as guaranteed
capacity.

#### Scenario: Unknown quota
- GIVEN a web-cookie endpoint with unknown quota
- WHEN allocation runs
- THEN it is added only as opportunistic fallback, never guaranteed capacity

