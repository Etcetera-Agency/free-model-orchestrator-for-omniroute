## 1. Proposal Context And Prompt

- [x] 1.1 Add a failing spec-bound test proving `aa-index-migration` loads `reference/prompts/aa-index-migration.md` through `LlmSiteConfig.prompt_path` and interpolates migration variables, not selected-model JSON.
- [x] 1.2 Implement prompt-path wiring for the migration site through the shared Instructor runtime.
- [x] 1.3 Add a failing spec-bound test for the migration context builder covering old/new index versions, metric distributions, active role thresholds, current combos, capacity bands, and percentile mapping.
- [x] 1.4 Implement the deterministic migration context builder and baseline audit snapshot persistence shape.

## 2. Model Resolver And Proposal Schema

- [x] 2.1 Add a failing spec-bound test proving `aa-index analyze` relies on the shared runtime resolver with fresh live quota checks and does not call a resolver-less model pre-check.
- [x] 2.2 Remove the duplicate resolver-less pre-check; let the shared runtime determine model availability and map no model to the existing fail-closed result.
- [x] 2.3 Add a failing spec-bound test for typed `MigrationProposalResponse` with only machine-used required fields: `index_version`, per-role `metric`, and per-role normalized `threshold_value`; optional `rationale` is audit-only.
- [x] 2.4 Implement typed response models and normalize persisted proposal payloads to the new schema.

## 3. Deterministic Validation And Repair

- [x] 3.1 Add failing spec-bound validation tests for wrong index version, unknown role, invalid metric, threshold outside new scale, insufficient combo size, insufficient independent quota pools, insufficient provider diversity, missing context/capability requirements, paid/unconfirmed endpoints, unhealthy endpoints, and exhausted live quota.
- [x] 3.2 Implement full operational validation with explicit error codes and no production mutation on failure.
- [x] 3.3 Add a failing spec-bound test for repair retries: first invalid proposal receives validation errors, second valid proposal is persisted, and the attempt report is stored.
- [x] 3.4 Implement bounded repair loop with at most three operational repair attempts and manual-review/fail-closed result after unrepaired invalid advice.

## 4. Rollout Gate And Audit

- [x] 4.1 Add a failing spec-bound test proving rollout revalidates the approved proposal against stored baseline plus current repository state before inserting threshold versions.
- [x] 4.2 Implement rollout-time validation and dry-run gate before threshold mutation.
- [x] 4.3 Add a failing spec-bound test proving drift between proposal and rollout prevents threshold changes and keeps migration out of `rolled_out`.
- [x] 4.4 Implement drift-safe failure handling and status/error persistence for blocked rollouts.
- [x] 4.5 Add or update `AICODE-NOTE:` anchors around the context builder, validator, and rollout gate.

## 5. Verification

- [x] 5.1 Run targeted tests for AA migration, Instructor runtime adapter, composition runtime, and spec coverage.
- [x] 5.2 Defer full `pytest` to the final all-slice verification pass per operator instruction.
- [x] 5.3 Update `openspec/TODO.md` if implementation discovers deferred scope, follow-up fixes, or known next steps.
- [x] 5.4 Use Code Simplifier before any commit and update `completion.review` if fixes are made during commit prep.
