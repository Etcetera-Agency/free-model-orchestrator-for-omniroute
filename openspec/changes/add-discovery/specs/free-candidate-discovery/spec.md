# free-candidate-discovery Specification

## ADDED Requirements

### Requirement: Candidate selection rule

The system SHALL mark a model as a free candidate when any of these hold, read
from the provider→model level of models.dev: listed input cost = 0 AND listed
output cost = 0; OR the normalized model id contains the standalone token `free`;
OR the normalized display name contains the standalone word `free`. The system
SHALL NOT use naive substring matching that catches `free` inside other words.

#### Scenario: Zero-cost provider offering
- GIVEN a models.dev provider offering with `cost.input = 0` and `cost.output = 0`
- WHEN the candidate filter runs
- THEN the model is recorded as a candidate with reason `zero_cost`

#### Scenario: Free token in model id
- GIVEN a model id containing the standalone token `free`
- WHEN the candidate filter runs
- THEN the model is recorded with reason `free_in_model_id`

#### Scenario: Missing cost is not free
- GIVEN a model with no `cost` field
- WHEN the candidate filter runs
- THEN the model is NOT recorded as zero-cost solely due to the missing field

### Requirement: Cost is read per provider

The system SHALL read pricing from the provider-keyed models.dev data, because the
same model id may be paid under one provider and free under another. The flat
top-level `models` map (which carries no `cost`) SHALL NOT be used for cost.

#### Scenario: Same model differs by provider
- GIVEN model id `X` priced above zero under provider A and zero under provider B
- WHEN candidates are built
- THEN only the provider-B endpoint is recorded as a zero-cost candidate

### Requirement: Candidate is a lead, not proof

The system SHALL treat name/id matches as candidates only; the final free decision
is made per OmniRoute provider/account by access classification and quota research.

#### Scenario: Name match stays unconfirmed
- GIVEN a model whose name contains `free` but has no confirmed quota
- WHEN the candidate enters classification
- THEN it is not activated until free access is confirmed
