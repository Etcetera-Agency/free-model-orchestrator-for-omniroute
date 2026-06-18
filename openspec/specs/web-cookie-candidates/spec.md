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

### Requirement: Live web-cookie/session acquisition

The system SHALL acquire web-cookie/session credentials only from explicitly
configured or eligible browser session sources; such endpoints SHALL NOT be
auto-discovered. After acquisition the system SHALL run a live health probe (text
probe and session health) and classify the result into a confirmed-usable session
or a specific failure mode: `expired`, `challenge`, `login_required`, or
`unsupported_auth`. A confirmed-usable session SHALL make the provider eligible
for fallback quota allocation at reduced weight (with the uncertainty penalty); a
non-confirmed result SHALL leave the endpoint unused.

#### Scenario: Configured session acquired and probed
- GIVEN a web-cookie endpoint with an explicitly configured session source
- WHEN acquisition runs
- THEN the session is loaded and a live health probe is run
- AND a healthy probe marks the session confirmed-usable

#### Scenario: Failure mode separated
- GIVEN a session whose probe fails
- WHEN the failure is classified
- THEN it is recorded as one of `expired`, `challenge`, `login_required`, or `unsupported_auth`
- AND the endpoint is not used

#### Scenario: Usable session becomes fallback capacity
- GIVEN a web-cookie endpoint with a confirmed-usable session
- WHEN allocation runs
- THEN the provider is eligible as reduced-weight fallback capacity
- AND its unknown quota is never counted as guaranteed capacity

#### Scenario: No auto-discovery
- GIVEN a web-cookie endpoint with no explicit session configuration
- WHEN acquisition runs
- THEN no session is acquired for it

