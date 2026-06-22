## ADDED Requirements

### Requirement: No-auth provider quota aliases

The system SHALL support explicit no-auth provider quota aliases when a no-auth
provider exposes the same model set and quota pool as an authenticated sibling
provider. An aliased no-auth provider SHALL inherit the sibling provider's model
expectations and quota rule and SHALL NOT be counted as independent capacity.

#### Scenario: Opencode shares opencode-zen quota
- GIVEN `opencode` is configured as a no-auth alias of `opencode-zen`
- WHEN quota research resolves quota for `opencode`
- THEN it uses the `opencode-zen` model and quota source
- AND `opencode` is marked as shared capacity with `opencode-zen`, not an
  independent quota pool

#### Scenario: Alias quota source missing
- GIVEN a no-auth provider has an authenticated sibling alias
- AND the sibling provider has no safe quota rule
- WHEN quota research resolves quota for the no-auth provider
- THEN the no-auth provider remains without usable quota
- AND no independent quota rule is inferred from the alias alone

### Requirement: Unknown no-auth provider calibration

The system SHALL mark no-auth providers with no reliable quota source as
calibration-required. A calibration-required provider SHALL NOT become usable
capacity until an operator places it first in a controlled combo, observes
OmniRoute token usage, and records the calibrated quota evidence. The recorded
evidence SHALL include observed token usage, inferred limit, reset window, and
hard-stop status before quota research can activate the rule.

#### Scenario: Unknown no-auth quota requires observation
- GIVEN a no-auth provider has no quota from registry, live quota, alias, or
  search
- WHEN quota research resolves the provider
- THEN the provider is marked calibration-required
- AND it is not treated as usable capacity

#### Scenario: Calibrated usage promotes quota
- GIVEN a calibration-required no-auth provider was placed first in a controlled
  combo
- AND OmniRoute token usage shows the limit, reset window, and hard-stop status
- WHEN the operator records the calibration evidence
- THEN quota research can activate the provider quota rule from that evidence

#### Scenario: Incomplete calibration stays inactive
- GIVEN a calibration-required no-auth provider has observed token usage
- AND the observation does not establish limit, reset window, or hard-stop status
- WHEN quota research evaluates the evidence
- THEN the provider remains calibration-required
- AND no usable quota is activated
