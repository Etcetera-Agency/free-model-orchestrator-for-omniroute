## ADDED Requirements

### Requirement: Fingerprint-backed account quota pools

The system SHALL expand any OmniRoute provider connection that exposes
`providerSpecificData.fingerprints` as registered account identities into one
provider-account scope per unique fingerprint before quota-pool grouping. Each
fingerprint scope SHALL use a stable quota pool key, SHALL preserve the parent
OmniRoute connection id in metadata, and SHALL count as confirmed independent
account capacity without hard-coding provider names.

#### Scenario: Fingerprints create independent pools
- GIVEN an OmniRoute provider connection contains three unique
  `providerSpecificData.fingerprints`
- WHEN account discovery groups quota pools
- THEN three confirmed fingerprint-backed quota pools are created for that
  provider
- AND provider capacity can sum the three per-account quotas

#### Scenario: Fingerprint pools feed allocation independently
- GIVEN an OmniRoute provider connection contains three unique
  `providerSpecificData.fingerprints`
- AND endpoints are discovered for that provider's models
- WHEN allocation builds candidate pools for combos
- THEN endpoints from separate fingerprint-backed pools can be placed into
  combos independently

#### Scenario: Duplicate fingerprints are deduplicated
- GIVEN a provider connection reports the same account fingerprint more than once
- WHEN account discovery expands fingerprint-backed scopes
- THEN only one provider-account scope and one quota pool are created for that
  fingerprint

#### Scenario: Missing fingerprints stay shared
- GIVEN a provider connection has no `providerSpecificData.fingerprints`
- AND it has no top-level independent account evidence
- WHEN account discovery groups quota pools
- THEN the connection remains on the existing shared-pool path
- AND capacity is not multiplied by the connection count
