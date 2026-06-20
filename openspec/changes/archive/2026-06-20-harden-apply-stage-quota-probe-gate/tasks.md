## 1. Derive quota safety in the stage

- [x] 1.1 Failing test: `_apply_stage` with a desired combo whose endpoint has a
      failing/stale/missing quota-safety record returns `unsafe_to_apply` (exit 5)
      and mutates no combo
- [x] 1.2 Failing test: `_apply_stage` with all desired endpoints quota-safe and
      probe-passed proceeds to apply
- [x] 1.3 Implement repository-backed `quota_safe` derivation for the desired
      combos (confirmed hard-stop, remaining above buffer)

## 2. Derive probe safety in the stage

- [x] 2.1 Failing test: a desired combo whose endpoint lacks a passing,
      non-stale probe result yields `probes_passed=False` → `unsafe_to_apply`
- [x] 2.2 Implement repository-backed `probes_passed` derivation

## 3. Fail closed

- [x] 3.1 Failing test: unknown/stale evidence (no row, or older than freshness
      window) maps to `False`, not a default pass
- [x] 3.2 Implement conservative defaulting and remove the hardcoded `True`
      literals from `_apply_stage`

## 4. Validation

- [x] 4.1 Targeted pytest for the apply stage and apply-guard tests
- [x] 4.2 Full `pytest -q`
- [x] 4.3 Bind new tests with `@pytest.mark.spec(...)` and shrink
      `tests/spec_coverage_pending.txt`
- [x] 4.4 `openspec validate harden-apply-stage-quota-probe-gate --strict`
