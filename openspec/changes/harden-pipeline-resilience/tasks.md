## 1. Pipeline continues past recoverable staleness

- [ ] 1.1 Write failing test: a `partial_stale` stage does not abort the run; all
      later stages still execute, bound to `pipeline-orchestration::Stale stage
      does not abort the run`.
- [ ] 1.2 Write failing test: a run that hit only staleness exits 2 while later
      stages still ran, bound to `pipeline-orchestration::Stale stage yields exit
      2 while later stages run`.
- [ ] 1.3 Write failing test: apply still excludes endpoints whose quota/probe
      evidence is stale, so continuing past staleness never produces an unsafe
      combo, bound to `pipeline-orchestration::Apply still excludes stale
      evidence`.
- [ ] 1.4 Remove `partial_stale` from `STOP_STATUSES`; keep hard-failure statuses
      stopping the run; confirm `worse_status` still reports exit 2 for staleness.

## 2. Per-endpoint resilience in quota research

- [ ] 2.1 Write failing test: one endpoint's research error does not stop research
      for the remaining endpoints, bound to `quota-research::One endpoint error
      does not stop research for the rest`.
- [ ] 2.2 Write failing test: when any endpoint failed, the stage reports
      `partial_stale` (not `external_dependency_failed`), bound to
      `quota-research::Per-endpoint failures mark the run partial`.
- [ ] 2.3 Change `_quota_research_stage` to record/skip a failing endpoint and
      continue the loop, returning `partial_stale` if any endpoint failed.

## 3. Apply gate rejects weak/assumed quota evidence

- [ ] 3.1 Write failing test: an endpoint whose only quota evidence is an assumed
      remaining (synthesized at classification, no live observation) does not pass
      the apply gate, bound to `combo-applier::Assumed remaining does not satisfy
      the apply gate`.
- [ ] 3.2 Write failing test: a record with no safety buffer is treated as the
      configured positive floor (not `0`), so a remaining at/below the floor
      fails closed, bound to `combo-applier::Zero safety buffer does not satisfy
      the apply gate`.
- [ ] 3.3 Add a configured minimum safety-buffer floor (`src/fmo/config.py`) and
      apply it in `_endpoint_quota_row_is_safe`; tag access-classification
      evidence as assumed vs live-observed so the gate can reject assumed
      remaining.

## 4. Close out

- [ ] 4.1 Run targeted then full `pytest`.
- [ ] 4.2 Remove the now-bound scenarios from `tests/spec_coverage_pending.txt`
      and `EXPECTED_ACTIVE_PENDING` in `tests/test_runtime_documentation.py`.
- [ ] 4.3 `openspec validate harden-pipeline-resilience --strict`.
