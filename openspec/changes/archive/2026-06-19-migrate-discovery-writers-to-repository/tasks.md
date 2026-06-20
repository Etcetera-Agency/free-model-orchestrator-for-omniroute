# Implementation Tasks

## 1. TDD Coverage

- [x] 1.1 Add failing persistence tests for provider/account/catalog snapshot
  round-trip through repository methods.
- [x] 1.2 Add failing persistence tests for free registry snapshot and free model
  definition upserts through repository methods.
- [x] 1.3 Add source-level regression tests proving `src/fmo/scanner.py` and
  `src/fmo/registry.py` do not embed table SQL for production writes.
- [x] 1.4 Add rollback/idempotency tests for scanner and registry repository
  writes.

## 2. Repository Methods

- [x] 2.1 Add provider catalog snapshot repository methods.
- [x] 2.2 Add free provider registry snapshot repository methods.
- [x] 2.3 Add repository helpers needed by scanner account/provider upserts.
- [x] 2.4 Add repository helpers needed by free model definition upserts.

## 3. Refactor Writers

- [x] 3.1 Refactor `CatalogScanner` to use repository transactions for
  provider/account/catalog/endpoint writes.
- [x] 3.2 Refactor registry persistence to use repository methods for snapshots
  and free model definitions.
- [x] 3.3 Remove direct psycopg write connection ownership from scanner and
  registry modules.
- [x] 3.4 Update production composition callers to pass repository-backed
  scanner/registry dependencies. No production caller existed yet; the active
  `wire-production-stage-modules` slice owns first production stage wiring and
  remains tracked in `openspec/TODO.md`.

## 4. Docs And Verification

- [x] 4.1 Clean `openspec/TODO.md` so it does not say there is no deferred work
  while active slices exist.
- [x] 4.2 Update `completion.review` with the repository migration result.
- [x] 4.3 Run targeted scanner, registry, persistence, composition, and spec
  coverage tests.
- [x] 4.4 Run `.venv/bin/python -m pytest -q`.
- [x] 4.5 Run `npx --yes @fission-ai/openspec@latest validate --all --strict`.
- [x] 4.6 Use Code Simplifier before finishing the implemented slice.
