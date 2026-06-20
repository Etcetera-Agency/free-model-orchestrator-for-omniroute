## 1. Shared adapter

- [x] 1.1 Failing test: all four sites call structured LLM through one adapter
  (OpenAI SDK → OmniRoute → model → Instructor → validated Pydantic).
- [x] 1.2 Failing test: prompts are redacted and per-site model limits applied.
- [x] 1.3 Implement the adapter: provider config, transport, structured-output
  mode, retries, assembly/redaction, per-site limits.

## 2. Fail-open and failure handling

- [x] 2.1 Failing test: smart-combo-reviewer and AA migration proceed
  deterministically when the LLM yields nothing usable (advisory fail-open).
- [x] 2.2 Failing test: malformed completions exercise the validator/repair path.
- [x] 2.3 Implement fail-open and deterministic failure handling.

## 3. Validation

- [x] 3.1 `openspec validate add-instructor-runtime-adapter --strict` passes.
