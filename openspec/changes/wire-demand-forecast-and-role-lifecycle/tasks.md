# Implementation Tasks

## 1. TDD Coverage

- [ ] 1.1 Add a failing effect test: allocation demand is forecast-derived, not a
  direct read of `expected_load["requests"]`.
- [ ] 1.2 Add a failing test: cold-start yields a non-zero demand floor for an
  unknown new role.
- [ ] 1.3 Add a failing test: the one-time historical reserve is applied exactly
  once; dependency cycles are handled deterministically.
- [ ] 1.4 Add a failing test: role-lifecycle reconcile applies removed-role grace
  and reactivation within grace, and bootstraps a brand-new role.
- [ ] 1.5 Bind scenarios with `@pytest.mark.spec(...)` and stage them in
  `tests/spec_coverage_pending.txt` until their tests land.

## 2. Implementation

- [ ] 2.1 Compute demand via `forecast` and feed it into the global allocator;
  remove the `expected_load["requests"]` shortcut.
- [ ] 2.2 Add a role-lifecycle reconcile step against the live registry with
  grace/reactivation/bootstrap; never hardcode roles.
- [ ] 2.3 Persist reconcile decisions and forecast inputs through the repository.

## 3. Verification

- [ ] 3.1 Run targeted tests: forecast, role_lifecycle, allocation, composition,
  pipeline.
- [ ] 3.2 Run `.venv/bin/python -m pytest -q`.
- [ ] 3.3 Run `npx --yes @fission-ai/openspec@latest validate --all --strict`.
- [ ] 3.4 Use Code Simplifier before finishing.
- [ ] 3.5 Update `completion.review` and shrink `tests/spec_coverage_pending.txt`.
