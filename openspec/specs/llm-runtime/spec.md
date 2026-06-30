# llm-runtime Specification

## Purpose
Define shared, non-authoritative LLM usage for Hermes role inspection.

## Requirements

### Requirement: LLM runtime is shared and non-authoritative
FMO SHALL use the shared runtime only for Hermes inspection and prompt-safe
structured hints. Missing or malformed LLM output SHALL not become model
capacity truth.

#### Scenario: Missing LLM provider config fails closed
- **WHEN** required LLM/OmniRoute credentials are missing
- **THEN** startup fails before dispatch.

#### Scenario: Edit one prompt
- **WHEN** one prompt file changes
- **THEN** prompt assembly uses that external file.

#### Scenario: PostgreSQL URL redaction
- **WHEN** a PostgreSQL URL with credentials appears in prompt context
- **THEN** credentials are redacted.

#### Scenario: Bearer token redaction
- **WHEN** bearer tokens appear in prompt context
- **THEN** token text is redacted.

#### Scenario: Cookie assignment redaction
- **WHEN** cookie assignments appear in prompt context
- **THEN** cookie values are redacted.

#### Scenario: Secret-like key removal
- **WHEN** secret-like keys appear in rendered context
- **THEN** their values are removed.

#### Scenario: Unresolved placeholder cleanup
- **WHEN** prompt placeholders cannot be resolved
- **THEN** unresolved secret placeholders are removed.

#### Scenario: Add or change runtime defaults
- **WHEN** runtime defaults change
- **THEN** all sites keep one shared runtime contract.

#### Scenario: Advisory site fails open
- **WHEN** a non-authoritative advisory LLM call fails
- **THEN** deterministic publisher work continues without its hint.

#### Scenario: All sites use the adapter
- **WHEN** LLM sites are called
- **THEN** calls pass through the shared adapter.

#### Scenario: Inspector sites fail closed without a resolver model
- **WHEN** an inspector site has no resolver-selected model
- **THEN** it does not call an arbitrary fallback model.

#### Scenario: Inspector sites use one resolver approach
- **WHEN** inspector model selection runs
- **THEN** all inspector sites use the same resolver policy.

#### Scenario: Malformed completion repaired or rejected
- **WHEN** a structured completion is malformed
- **THEN** it is repaired within bounds or rejected.
