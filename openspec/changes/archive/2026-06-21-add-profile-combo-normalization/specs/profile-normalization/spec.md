# profile-normalization Specification

## ADDED Requirements

### Requirement: Slots are normalized to existing combos

The system SHALL provide a normalization operation that rewrites every Hermes
profile model slot (main, `auxiliary.<slot>`, and gateway/platform auxiliary) so
it routes through an existing OmniRoute combo. A slot that points at a raw
`provider/model`, or at a combo id absent from the live combo set, SHALL be
rewritten to the existing combo whose members include the slot's **canonical
model** (provider stripped). When no existing combo contains that canonical
model, the slot SHALL be rewritten to the **default combo** — the main combo of
the `default` profile. A slot already pointing at an existing `fmo-` combo, or set
to `auto`/empty, SHALL be left unchanged. The operation SHALL NOT create or
delete OmniRoute combos.

#### Scenario: Raw slot maps to combo with same canonical model
- GIVEN a slot `vision: google/gemini-2.5-flash` and an existing combo whose
  members include a `gemini-2.5-flash` endpoint (any provider)
- WHEN normalization runs
- THEN the slot is rewritten to that combo
- AND the provider of the raw model is ignored in the match

#### Scenario: Missing combo falls back to default profile combo
- GIVEN a slot pointing at a combo id absent from OmniRoute and no existing combo
  contains the slot's canonical model
- WHEN normalization runs
- THEN the slot is rewritten to the `default` profile's main combo
- AND no new combo is created

#### Scenario: Conforming and auto slots are untouched
- GIVEN one slot on an existing `fmo-` combo and one slot on `auto`/empty
- WHEN normalization runs
- THEN both slots are left unchanged

### Requirement: Normalization is safe and reversible

The normalization operation SHALL support a dry-run that reports planned rewrites
and writes nothing. On apply it SHALL back up each `config.yaml` before modifying
it and SHALL rewrite atomically, preserving all other configuration in the file.

#### Scenario: Dry-run writes nothing and backs up config
- WHEN normalization runs with `--dry-run`
- THEN it reports the planned slot rewrites
- AND no `config.yaml` and no backup is written

#### Scenario: Apply backs up before atomic rewrite
- GIVEN at least one slot to rewrite
- WHEN normalization applies
- THEN each touched `config.yaml` is backed up first
- AND the file is rewritten atomically with the resolved combo and all other keys
  preserved
