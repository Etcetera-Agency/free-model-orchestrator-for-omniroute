## 1. Specification

- [x] 1.1 Add account-discovery requirements for fingerprint-backed account scopes.
- [x] 1.2 Track executable-test follow-up in `openspec/TODO.md` and `tests/spec_coverage_pending.txt`.
- [x] 1.3 Validate the OpenSpec change strictly.

## 2. Implementation

- [x] 2.1 Add a failing fixture-backed test proving a provider connection with three fingerprints creates three independent quota pools.
- [x] 2.2 Add a failing allocation test proving endpoints from separate fingerprint pools can be placed into combos independently.
- [x] 2.3 Add a failing test proving duplicate fingerprints are deduplicated before capacity calculation.
- [x] 2.4 Add a failing test proving providers without fingerprints stay on the shared-pool path.
- [x] 2.5 Expand `providerSpecificData.fingerprints` into deterministic provider-account scopes during account discovery without hard-coding provider names.
- [x] 2.6 Persist fingerprint scopes with stable provider-account refs, quota pool membership, and parent connection metadata.
- [x] 2.7 Ensure endpoint discovery and allocation consume fingerprint provider accounts so quota capacity and combo targets can fan out per account.
- [x] 2.8 Remove covered `account-discovery::*` entries from `tests/spec_coverage_pending.txt`.
