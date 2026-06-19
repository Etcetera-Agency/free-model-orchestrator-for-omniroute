# Change: Align docs with actual runtime (housekeeping)

## Why

Documentation drifted from the shipped runtime and from the change archive:

- `openspec/TODO.md` lists `add-real-source-ingestion-tests` as **"(active)"**,
  but it is archived and there are zero active changes — the status is wrong.
- `README.md` "Current Scope" / "Safety Model" advertise the scheduler, the
  apply guard, and a functional per-stage CLI as if shipped, while the production
  path does not yet wire them (addressed by `compose-production-pipeline`,
  `derive-apply-preconditions`, `run-scheduler-process`, `persist-metadata-sync`).
- `completion.review` describes the old edge-case-coverage slice, not the current
  state.
- The TODO "Deferred Work" item (migrate `scanner.py` / `registry.py` direct SQL
  to the repository layer; then drop `data-model::Repository is the only writer`
  and `persistence::Stages do not embed schema SQL` from the allowlist) is still
  open and should be tracked accurately.

This is a documentation-only housekeeping slice. It carries a small
`runtime-documentation` spec delta so the active change remains valid under
`openspec validate --all --strict`.

## What Changes

- Fix `openspec/TODO.md`: correct active/archived status; reflect that production
  wiring is tracked by slices 1–4; keep the deferred scanner/registry repository
  migration accurately listed.
- Refresh `completion.review` to describe the current review outcome.
- Update `README.md` to distinguish shipped component logic from production wiring
  that lands in slices 1–4 (or mark those capabilities as wired once they land).

## Impact

- Affected specs: `runtime-documentation`.
- Affected code: `openspec/TODO.md`, `completion.review`, `README.md` (docs only).
- Best sequenced **after** slices 1–4 so the docs describe the wired runtime; can
  land earlier purely to correct the false "(active)" status and stale review.
