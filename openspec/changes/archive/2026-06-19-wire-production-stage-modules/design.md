## Context

`build_canonical_stages()` currently builds the canonical stage list, but every
stage except metadata sync uses `_successful_stage(name)`. That satisfies order
tests while skipping the actual orchestrator behavior.

## Goals

- Production runtime invokes existing domain modules for each canonical stage.
- Per-stage CLI commands call the same stage adapters as `full`.
- Tests observe domain adapter calls and persisted outcomes, not only stage
  names.
- Existing exit-code semantics stay unchanged.

## Non-Goals

- Rewrite domain algorithms.
- Add paid-provider behavior.
- Call `/api/combos/test`.
- Keep compatibility shims for placeholder stage behavior.

## Decisions

- Stage adapters live near composition and call existing modules; they do not
  duplicate module logic.
- The composition root owns dependencies: repository, OmniRoute client, config,
  and any stage adapter collaborators.
- Stage adapters return `StageResult`; they translate domain errors to existing
  statuses.
- Tests use fake adapters/clients and DB assertions to prove composed commands
  call real stage paths.

## Pseudocode

```python
def compose_runtime(config, adapters=None):
    repository = Repository(Database(config.database_url))
    client = OmniRouteClient(base_url=config.omniroute_url)
    deps = StageDependencies(repository=repository, client=client, config=config)
    stages = build_canonical_stages(deps, adapters=adapters)
    return ComposedRuntime(repository, client, stages, config.hermes_inventory_cron)

def build_canonical_stages(deps, adapters=None):
    return [
        Stage("external-metadata-sync", metadata_stage(deps, adapters.metadata)),
        Stage("free-candidate-discovery", discovery_stage(deps, adapters.discovery)),
        Stage("model-matching", matcher_stage(deps, adapters.matcher)),
        Stage("quota-research", quota_research_stage(deps, adapters.quota_research)),
        Stage("access-classification", access_stage(deps, adapters.access)),
        Stage("probing", probe_stage(deps, adapters.probe)),
        Stage("telemetry-sync", telemetry_stage(deps, adapters.telemetry)),
        Stage("quota-sync", quota_sync_stage(deps, adapters.quota_sync)),
        Stage("role-scoring", scoring_stage(deps, adapters.scoring)),
        Stage("allocation", allocation_stage(deps, adapters.allocation)),
        Stage("diff", diff_stage(deps, adapters.diff)),
        Stage("apply", apply_stage(deps, adapters.apply)),
        Stage("audit", audit_stage(deps, adapters.audit)),
    ]

def run_command(command, args):
    stages = stages_for_command(command, self.stages)
    return PipelineRunner(self.repository, stages=stages).run(
        trigger=command,
        run_type=run_type(command),
    )

def discovery_stage(deps, adapter):
    try:
        result = adapter.scan(deps.client, deps.repository)
    except ExternalFetchError as exc:
        return StageResult(status="external_dependency_failed", reason=exc.reason)
    if result.partial_stale:
        return StageResult(status="partial_stale", reason=result.reason)
    return StageResult(status="success", changed=result.changed, idempotency_key=result.key)
```

## Risks / Mitigations

- Risk: stage adapters expose missing repository methods.
  Mitigation: implement missing repository methods in small vertical slices and
  keep uncovered follow-up work in `openspec/TODO.md`.
- Risk: `full` becomes stricter and starts failing where placeholders passed.
  Mitigation: preserve exit-code mapping and add targeted tests for each failure
  class.

## Migration Plan

1. Add failing tests around composed stage calls.
2. Replace placeholder stages one stage group at a time.
3. Run targeted tests after each stage group.
4. Run full pytest and OpenSpec validation.
5. Update `completion.review` and `openspec/TODO.md` if additional future work
   is discovered.
