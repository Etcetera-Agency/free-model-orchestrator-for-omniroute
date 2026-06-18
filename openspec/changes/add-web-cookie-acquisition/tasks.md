## 1. Session acquisition and live probes

- [ ] 1.1 Failing test: only explicitly configured/eligible session sources are
  loaded (never auto-discovered).
- [ ] 1.2 Failing test: live health probe results separate expired / challenge /
  login / unsupported-auth failure modes.
- [ ] 1.3 Failing test: a confirmed-usable session makes the provider eligible
  for fallback (reduced-weight) allocation; non-confirmed stays unused.
- [ ] 1.4 Implement acquisition and the live probe/health classification.

## 2. Fixtures

- [ ] 2.1 Record realistic session/probe fixtures for each failure mode and tests.

## 3. Validation

- [ ] 3.1 `openspec validate add-web-cookie-acquisition --strict` passes.
