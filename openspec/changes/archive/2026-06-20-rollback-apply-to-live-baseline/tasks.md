## 1. Capture the live baseline

- [x] 1.1 Failing test: when the live combo state at apply time differs from the
      diff-time `before`, a smoke failure restores the live baseline (not the
      stale `before`)
- [x] 1.2 Implement capture of the pre-mutation live state and reuse it as the
      rollback baseline

## 2. Drift path on divergence

- [x] 2.1 Failing test: when live state differs from the diff-time `before`, the
      apply follows the drift/conflict path instead of overwriting without force
- [x] 2.2 Implement the divergence-to-drift handoff

## 3. Validation

- [x] 3.1 Targeted pytest for apply/rollback
- [x] 3.2 Full `pytest -q`
- [x] 3.3 Bind tests with `@pytest.mark.spec(...)` and shrink the pending list
- [x] 3.4 `openspec validate rollback-apply-to-live-baseline --strict`
