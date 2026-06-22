# pipeline-orchestration Specification

## ADDED Requirements

### Requirement: Quota research is triggered by free-model changes

The pipeline SHALL run the quota-research stage only when a free-model change is
detected since the prior run — a newly free model, or an existing model whose
free/0-cost status changed — restricted to models reachable via an existing
OmniRoute connection; otherwise the stage is skipped as an idempotent no-change.
On a triggered run the pipeline SHALL continue through scoring, allocation, diff
and apply so that a model that gained free status is added as a member of any
existing combo whose band and capability it fits (without creating a combo), and
a model that lost free status is dropped from combos on rebalance and its quota
rule is deactivated.

#### Scenario: Quota research is triggered by new free models
- GIVEN a full run where a new confirmed-free model reachable via a connection
  appeared since the prior run
- WHEN the pipeline runs
- THEN quota research performs a full recalc
- AND the run continues so the new model is added to a fitting existing combo on
  rebalance

#### Scenario: No new free model leaves quota research skipped
- GIVEN a full run with no free-model change since the prior run
- WHEN the pipeline runs
- THEN quota research is skipped as an idempotent no-change
- AND the remaining daily safety stages still run

#### Scenario: Lost-free-status model is dropped on rebalance
- GIVEN a model that was a member of an existing combo and whose free/0-cost
  status changed to paid since the prior run
- WHEN the triggered run rebalances
- THEN the model is dropped from the combo (it fails the confirmed-free gates)
- AND its quota rule is deactivated, while the provider-model itself is not deleted
