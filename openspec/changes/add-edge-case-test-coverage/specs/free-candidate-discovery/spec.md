# free-candidate-discovery Specification

## MODIFIED Requirements

### Requirement: Candidate selection rule

The system SHALL mark a provider endpoint as a candidate only when models.dev
shows zero input and zero output cost, the model id/name has a bounded free token
signal, or provider docs declare a free tier. Substrings inside unrelated words
or platform names such as `freedom`, `carefree`, or `freebsd` SHALL NOT count as
free-token signals. Non-object cost data or only one zero cost side SHALL NOT
count as zero cost.

#### Scenario: False free token
- GIVEN a model id contains `freedom`, `carefree`, or `freebsd`
- WHEN candidate detection runs
- THEN it is not treated as a free token signal

#### Scenario: Cost is not an object
- GIVEN cost metadata is not a dict/object
- WHEN candidate detection runs
- THEN it is not treated as zero cost

#### Scenario: Only input cost is zero
- GIVEN input cost is zero but output cost is not zero
- WHEN candidate detection runs
- THEN it is not treated as zero cost

#### Scenario: Multiple signals collapse
- GIVEN two or more candidate signals are present
- WHEN candidate evidence is recorded
- THEN the signal is collapsed to `multiple_signals`
