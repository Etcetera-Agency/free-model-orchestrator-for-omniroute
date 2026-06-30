# cli-and-operations Specification

## Purpose
Define the current publisher-only CLI commands and dispatch behavior.

## Requirements

### Requirement: Current CLI surface dispatches real publisher work
The CLI SHALL expose only current publisher/runtime commands and SHALL route
stage commands through the injected or composed pipeline runner.

#### Scenario: Stage command invokes its stage
- **WHEN** a current stage command is invoked
- **THEN** the pipeline runner receives that command and parsed flags.

#### Scenario: Dry-run validation
- **WHEN** a command is invoked with `--dry-run`
- **THEN** dry-run intent is passed to the stage without combo writes.

#### Scenario: Dry-run runs the stage, not an unconditional success
- **WHEN** dry-run stage execution fails
- **THEN** the CLI returns the stage failure code.

#### Scenario: Normalize command dispatches to normalization
- **WHEN** `normalize-profiles` is invoked
- **THEN** the profile normalizer handles the command.

#### Scenario: Normalize dry-run reports without writing
- **WHEN** `normalize-profiles --dry-run` is invoked
- **THEN** the result reports planned rewrites without mutation.
