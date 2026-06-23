# hermes-inventory Specification Delta

## MODIFIED Requirements

### Requirement: Inspector runs via Instructor with limited scope

The Hermes role Inspector SHALL run through the same Instructor runtime as the
other structured-LLM steps (OpenAI SDK -> OmniRoute -> model -> Instructor ->
validated Pydantic forecast) and SHALL return only a forecast (runs, calls,
tokens, concurrency, confidence, assumptions); it SHALL NOT select models or
change quota attribution, and SHALL receive no secrets in its prompt. The Hermes
forecast Inspector and Hermes intelligence Inspector SHALL NOT set `site.model`
to any hardcoded fabricated combo. They SHALL leave the model unset so the shared
runtime resolver selects a concrete provider model at call time. In production
that resolver is `select_llm_model`, which returns the selected free provider
model's `provider_model_id`. When no resolver-selected provider model is
available, the adapter SHALL fail closed as `llm_model_unavailable` instead of
calling a fabricated inspector combo.

#### Scenario: Inspector output
- GIVEN the Inspector is asked to forecast a role
- WHEN it responds via Instructor
- THEN it returns a validated forecast only, with no model choice or quota change

#### Scenario: Inspector uses resolver-selected provider model
- GIVEN the shared runtime resolver selects provider model `provider/model-a`
- WHEN the Hermes forecast Inspector or Hermes intelligence Inspector calls the
  Instructor runtime
- THEN the outbound model id is `provider/model-a`
- AND no fabricated Inspector combo is used

#### Scenario: Resolver-less inspector fails closed
- GIVEN no resolver-selected provider model is available
- WHEN the Hermes forecast Inspector or Hermes intelligence Inspector calls the
  Instructor runtime
- THEN the call fails closed as `llm_model_unavailable`
- AND no fabricated Inspector combo is used
