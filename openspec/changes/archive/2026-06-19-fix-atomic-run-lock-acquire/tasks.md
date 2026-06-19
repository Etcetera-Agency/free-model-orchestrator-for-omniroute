# Implementation Tasks

## 1. Tests First

- [x] 1.1 Add a scheduler repository test that opens two independent PostgreSQL
  connections and attempts to acquire the same lock concurrently.
- [x] 1.2 Assert exactly one acquisition returns a token and exactly one active
  held row exists for the logical lock name.
- [x] 1.3 Add migration/schema coverage that verifies fresh installs and
  migrated databases include the active-lock uniqueness rule.

## 2. Schema

- [x] 2.1 Add the partial unique active-lock index to
  `reference/db/schema.sql`.
- [x] 2.2 Add the next ordered migration under `reference/db/migrations/`.
- [x] 2.3 Keep released lock rows and historical sync runs unconstrained.

## 3. Implementation

- [x] 3.1 Replace `LockRepository.acquire()` check-then-insert with atomic
  `INSERT ... ON CONFLICT DO NOTHING ... RETURNING id`.
- [x] 3.2 Keep `RunLockManager.acquire()` returning `acquired=False` when the
  insert returns no row.
- [x] 3.3 Keep `LockRepository.release()` row-backed and idempotent for the
  held token.

## 4. Verification

- [x] 4.1 Run `.venv/bin/python -m pytest tests/test_scheduler.py`.
- [x] 4.2 Run `.venv/bin/python -m pytest`.
- [x] 4.3 Run `openspec validate fix-atomic-run-lock-acquire --strict` if the
  OpenSpec CLI is available in the environment.
- [x] 4.4 Use Code Simplifier before finalizing implementation.
- [x] 4.5 Update `completion.review` if implementation review finds and fixes
  additional issues.
