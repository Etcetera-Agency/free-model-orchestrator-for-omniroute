## 1. Capture the live baseline

- [ ] 1.1 Failing test: when the live combo state at apply time differs from the
      diff-time `before`, a smoke failure restores the live baseline (not the
      stale `before`)
- [ ] 1.2 Implement capture of the pre-mutation live state and reuse it as the
      rollback baseline

## 2. Drift path on divergence

- [ ] 2.1 Failing test: when live state differs from the diff-time `before`, the
      apply follows the drift/conflict path instead of overwriting without force
- [ ] 2.2 Implement the divergence-to-drift handoff

## 3. Validation

- [ ] 3.1 Targeted pytest for apply/rollback
- [ ] 3.2 Full `pytest -q`
- [ ] 3.3 Bind tests with `@pytest.mark.spec(...)` and shrink the pending list
- [ ] 3.4 `openspec validate rollback-apply-to-live-baseline --strict`
