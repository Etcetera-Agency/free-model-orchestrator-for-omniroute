# scheduler Specification

## MODIFIED Requirements

### Requirement: Daily orchestration order

The daily scheduler SHALL sync external metadata before dependent pipeline
stages. It SHALL fetch models.dev before free candidate discovery and SHALL fetch
Artificial Analysis with a configured API key before role scoring and AA
index migration checks.

#### Scenario: External metadata before discovery and scoring
- GIVEN the daily scheduler starts a full run
- WHEN the run reaches metadata sync
- THEN models.dev catalog sync completes before candidate discovery
- AND authenticated Artificial Analysis sync completes before scoring and AA index migration detection

#### Scenario: Metadata sync failure is conservative
- GIVEN models.dev or Artificial Analysis metadata sync fails
- WHEN the daily scheduler evaluates dependent stages
- THEN dependent stages do not consume partial failed payloads
- AND the run records an external dependency failure
