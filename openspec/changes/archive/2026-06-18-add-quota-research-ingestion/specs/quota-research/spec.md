## ADDED Requirements

### Requirement: Production quota research client

The system SHALL run quota research against the live OmniRoute search surface
(`POST /v1/search` with `gemini-grounded-search`) using configured credentials,
bounded retries, and immutable snapshot persistence of the returned
`answer.text`, unless a research result is explicitly injected. Structured
extraction SHALL run over the real search result. When the search source is
unavailable, the system SHALL fail conservatively and SHALL NOT produce a quota
rule from missing data.

#### Scenario: Live search performed
- GIVEN an endpoint needs a quota rule and no research result is injected
- WHEN quota research runs
- THEN `/v1/search` is called with `gemini-grounded-search` and configured auth
- AND the `answer.text` is persisted as an immutable snapshot before extraction

#### Scenario: Search unavailable
- GIVEN the search source is unavailable
- WHEN quota research runs
- THEN no quota rule is produced
- AND the endpoint remains without confirmed quota
