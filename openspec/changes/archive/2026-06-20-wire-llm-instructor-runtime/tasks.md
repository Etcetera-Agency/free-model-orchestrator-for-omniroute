# Implementation Tasks

## 1. TDD Coverage

- [x] 1.1 Add a failing test: production composition constructs the Instructor
  client via `instructor.from_openai` from validated config (base URL from
  `OMNIROUTE_URL`, api key) and exposes the runtime to the wired sites; the model
  is supplied by the selection procedure, and the test stubs only the OpenAI
  client transport.
- [x] 1.2 Add a failing test: the `quota-research` stage uses
  `run_quota_inspector` to extract the claim when the runtime is available.
- [x] 1.3 Add a failing test: when the inspector is unavailable or returns an
  unusable claim, the stage falls open to `extract_summary_claim` and still
  applies `summary_confidence_cap`.
- [x] 1.4 Add a failing test: the advisory `smart-combo-reviewer` runs over the
  computed diff and its output is recorded but the applied diff is byte-identical
  whether or not the reviewer succeeds.
- [x] 1.5 Add a failing test: env validation rejects missing/invalid LLM provider
  config keys.
- [x] 1.6 Add a failing test: the model-selection procedure selects the
  confirmed-free model with the maximum AA `intelligence_index` (healthy, with
  quota), falls to the next model by descending `intelligence_index` on
  unavailability, then to a configured confirmed-free bootstrap model, then to
  no-LLM mode — never routing to a paid or unconfirmed model, and never building a
  dedicated combo.
- [x] 1.7 Bind scenarios with `@pytest.mark.spec(...)` and stage them in
  `tests/spec_coverage_pending.txt` until their tests land.

## 2. Implementation

- [x] 2.1 Add `instructor` to `pyproject.toml` dependencies and add LLM
  provider/site config to `config.py` and `bootstrap.py` startup validation
  (provider base url, api key, per-site call limits, bootstrap model id).
- [x] 2.2 Build the production Instructor client with `instructor.from_openai`
  in `composition.py`, wrap it in `SharedInstructorRuntime`, and pass the runtime
  into the `quota-research` stage and the diff/advisory hook.
- [x] 2.3 Implement the model-selection/substitution resolver (highest AA
  `intelligence_index` healthy confirmed-free model → next by descending index →
  bootstrap model → no-LLM) and substitute its result as the per-call model;
  assert it never resolves to a paid/unconfirmed model and never builds a
  dedicated combo.
- [x] 2.4 Route quota claim extraction through `run_quota_inspector` with the
  deterministic regex extractor as the fail-open fallback.
- [x] 2.5 Invoke `run_combo_review` as an advisory, non-blocking pass; persist the
  advisory result without mutating the applied diff.

## 3. Verification

- [x] 3.1 Run targeted tests: llm_runtime, quota_research, smart_review,
  composition, pipeline.
- [x] 3.2 Run `.venv/bin/python -m pytest -q`.
- [x] 3.3 Run `npx --yes @fission-ai/openspec@latest validate --all --strict`.
- [x] 3.4 Use Code Simplifier before finishing.
- [x] 3.5 Update `completion.review` and shrink `tests/spec_coverage_pending.txt`.
