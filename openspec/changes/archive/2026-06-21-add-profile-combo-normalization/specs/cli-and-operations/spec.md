# cli-and-operations Specification

## ADDED Requirements

### Requirement: Profile normalization command

The system SHALL provide a `normalize-profiles` command that runs the profile →
combo normalization and returns that operation's real outcome and exit code. It
SHALL honor `--dry-run` (report only, no writes). It SHALL NOT return an
unconditional success.

#### Scenario: Normalize command dispatches to normalization
- WHEN an operator runs `normalize-profiles`
- THEN the normalization operation runs over all profiles' slots
- AND the command exit code reflects the operation's outcome

#### Scenario: Normalize dry-run reports without writing
- WHEN an operator runs `normalize-profiles --dry-run`
- THEN planned rewrites are reported
- AND no profile `config.yaml` is modified
