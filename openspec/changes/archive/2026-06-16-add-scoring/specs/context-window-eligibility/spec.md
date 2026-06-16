# context-window-eligibility Specification

## ADDED Requirements

### Requirement: Effective context per endpoint

The system SHALL compute `effective_context_window` as the minimum of the known
sources (canonical, provider catalog, connection override, verified probe,
OmniRoute limit); unknown values do not enter the min but lower confidence. If no
reliable value exists, context status is `unknown`.

#### Scenario: Provider smaller than canonical
- GIVEN canonical context 128K and provider catalog 64K
- WHEN effective context is computed
- THEN it is 64K

### Requirement: Context as hard filter, one combo per role

The system SHALL exclude an endpoint when `effective_context_window <
role.minimum_context_window` or `effective_max_output_tokens <
role.minimum_output_tokens`. A larger context SHALL add no score bonus and SHALL
NOT spawn a separate combo — each role has exactly one combo.

#### Scenario: Below minimum
- GIVEN a role minimum of 64K and an endpoint effective context 32K
- WHEN eligibility runs
- THEN the endpoint is excluded from that role

#### Scenario: Far above minimum
- GIVEN a role minimum of 64K and an endpoint with 1M context
- WHEN eligibility runs
- THEN the endpoint is eligible with no bonus and no extra combo

### Requirement: Unknown context excluded

The system SHALL exclude an endpoint with unknown context from any role that has
a minimum, unless an explicit manual override is set.

#### Scenario: Unknown context, no override
- GIVEN an endpoint with `context_status = unknown` and no override
- WHEN eligibility runs for a role with a minimum
- THEN the endpoint is excluded
