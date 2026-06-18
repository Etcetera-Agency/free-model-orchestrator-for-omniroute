## 1. Shared adapter

- [ ] 1.1 Failing test: all four sites call structured LLM through one adapter
  (OpenAI SDK → OmniRoute → model → Instructor → validated Pydantic).
- [ ] 1.2 Failing test: prompts are redacted and per-site model limits applied.
- [ ] 1.3 Implement the adapter: provider config, transport, structured-output
  mode, retries, assembly/redaction, per-site limits.

## 2. Fail-open and failure handling

- [ ] 2.1 Failing test: smart-combo-reviewer and AA migration proceed
  deterministically when the LLM yields nothing usable (advisory fail-open).
- [ ] 2.2 Failing test: malformed completions exercise the validator/repair path.
- [ ] 2.3 Implement fail-open and deterministic failure handling.

## 3. Validation

- [ ] 3.1 `openspec validate add-instructor-runtime-adapter --strict` passes.
