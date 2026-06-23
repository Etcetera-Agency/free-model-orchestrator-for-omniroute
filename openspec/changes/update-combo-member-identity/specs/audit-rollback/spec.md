## MODIFIED Requirements

### Requirement: Explainability per assignment

The system SHALL store, for each endpoint-to-role or endpoint-to-cell
assignment, why it was selected, why nearby candidates were not selected, quota
impact, diversity impact, score components, and the structured combo member
identity used to render the OmniRoute payload.

#### Scenario: Inspect an assignment
- GIVEN an endpoint assigned as a combo primary or fallback
- WHEN the assignment is audited
- THEN the audit shows the endpoint id, provider/model, provider account,
  connection id when pinned, quota pool, canonical model/family, score
  components, quota impact, and diversity impact
