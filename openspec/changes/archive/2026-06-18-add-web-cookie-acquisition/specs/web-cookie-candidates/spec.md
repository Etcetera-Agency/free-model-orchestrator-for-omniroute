## ADDED Requirements

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
