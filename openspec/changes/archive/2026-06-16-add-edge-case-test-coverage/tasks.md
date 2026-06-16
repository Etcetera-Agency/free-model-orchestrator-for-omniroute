# Implementation Tasks (TDD)

Write each regression test first (red/green check), then only change production
code when current behavior disagrees with the requirement. Use isolated repo
`.venv`. Do not run human run. Do not run `check_scope_creep`.

## Tasks

- [x] 1. TEST: OmniRoute client GET retry exhaustion, non-retry 4xx/5xx, bad `Retry-After`, and safe URL joining.
- [x] 2. TEST: config validation branches for URLs, DB URL, inventory modes, cron fields, filesystem paths, command/http mode, and health payload type.
- [x] 3. TEST: access classifier fail-closed, quota preconditions, expired promotion, exhausted quota boundary, and exclusion priority.
- [x] 4. TEST: scoring eligibility reasons, degenerate normalization, and missing latency source behavior.
- [x] 5. TEST: quota manager unknown remaining, negative effective remaining, and hard-stop rejection.
- [x] 6. TEST: allocation zero-capacity oversubscription, no-capacity role omission, heavy-role pool separation, and stable-order missing-score guard.
- [x] 7. TEST: smart review instructor failure, trigger skip, diff validation errors, and idempotent add.
- [x] 8. TEST: candidate detection false positives, non-dict/partial zero cost, and multiple signal collapse.
- [x] 9. TEST: web-cookie probe/session/auth-source/capability negative branches.
- [x] 10. TEST: LLM runtime redaction patterns, secret-like context key removal, and unresolved placeholder cleanup.
- [x] 11. TEST: state machine forbidden combo transitions plus account merge/capacity fallback branches.
- [x] 12. TEST: scanner removal guards, snapshot unchanged semantics, probe error table, probe eligibility, and failed probe response branches.
- [x] 13. FIX: Apply minimal production fixes for any failing requested behavior; update `completion.review` for each fix.
- [x] 14. VALIDATE: Run targeted tests, full `pytest`, and `openspec validate --all --strict`.
