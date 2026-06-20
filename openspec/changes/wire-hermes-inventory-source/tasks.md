# Implementation Tasks

## 1. TDD Coverage

- [ ] 1.1 Add a failing effect test: the `hermes-inventory` stage gathers roles,
  consumers, schedules, and observed `calls_per_run` and persists them.
- [ ] 1.2 Add a failing test: the selected mode adapter
  (filesystem/command/http) is used per `HERMES_INVENTORY_MODE`.
- [ ] 1.3 Add a failing test: the Inspector runs prompt-only over the shared
  runtime and never reads sources directly.
- [ ] 1.4 Add a failing test: allocation consumes Hermes-derived demand, not only
  static `expected_load`.
- [ ] 1.5 Add a failing test: missing required Hermes env fails closed; an unknown
  role bootstraps via the dynamic-role path.
- [ ] 1.6 Bind scenarios with `@pytest.mark.spec(...)` and stage them in
  `tests/spec_coverage_pending.txt` until their tests land.

## 2. Implementation

- [ ] 2.1 Add a `hermes-inventory` stage to the canonical order before
  `role-scoring`.
- [ ] 2.2 Wire the deterministic gather adapters and persist roles/consumers/
  schedules/cadence through the repository.
- [ ] 2.3 Run `run_inspector` over the shared runtime as a prompt-only demand
  estimate; apply change-driven refresh on schedule changes.

## 3. Verification

- [ ] 3.1 Run targeted tests: hermes_inventory_real_shapes, composition,
  pipeline, allocation.
- [ ] 3.2 Run `.venv/bin/python -m pytest -q`.
- [ ] 3.3 Run `npx --yes @fission-ai/openspec@latest validate --all --strict`.
- [ ] 3.4 Use Code Simplifier before finishing.
- [ ] 3.5 Update `completion.review` and shrink `tests/spec_coverage_pending.txt`.
