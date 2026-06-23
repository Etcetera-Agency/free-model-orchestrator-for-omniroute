# Design: Update AA Index Migration Inspector

## Context

`aa-index-migration` is one of the four shared Instructor sites. Its job is
advisory: inspect a new Artificial Analysis index version and propose threshold
policies. Deterministic code owns facts, validation, approval, rollout, and
rollback.

The current implementation has three important gaps:

- `run_migration_agent` does not pass `prompt_path`, so the external prompt file
  is not used.
- `aa-index analyze` calls `select_llm_model(repository, config)` without the
  live quota client even though production composition already wires a shared
  resolver with that client.
- Validation only checks metric name, minimum count, and coarse quota/quality
  booleans; rollout does not re-run validation from persisted state.

## Goals

- Make the real migration prompt editable and effective.
- Give the inspector enough context to make useful threshold advice.
- Keep all LLM output untrusted until deterministic validation, dry-run, and
  approval.
- Keep no-LLM and invalid-advice paths fail-closed for threshold changes.
- Preserve the project invariant: no paid, unconfirmed, unhealthy, exhausted, or
  quota-unsafe endpoint may become eligible because of LLM advice.

## Non-Goals

- No new autonomous agent framework.
- No live LLM calls in unit tests.
- No automatic threshold rollout without operator approval.
- No paid fallback model and no dedicated migration combo.

## Decisions

- Use the existing shared `SharedInstructorRuntime.complete` path with
  `LlmSiteConfig(prompt_path=...)`. This keeps prompt redaction, unresolved
  placeholder cleanup, response validation, and model resolution in one place.
- Move `aa-index analyze` model availability probing into the shared runtime call.
  If the resolver cannot produce a model, `run_migration_agent` returns advisory
  unavailable and the command maps that to the existing failure code without DB
  mutation.
- Store context and baseline facts separately from LLM output. The prompt gets
  summarized facts; `baseline_snapshot_json` stores the deterministic source
  snapshot needed for audit and rollout validation.
- Validate before persistence and again before rollout. The second validation
  uses current repository state plus the stored baseline to catch drift between
  proposal and rollout.
- Repair loop is operational, not free-form. The validator emits compact error
  codes and safe context; the next LLM attempt receives the original context plus
  those errors. After three failed attempts, persist no rollout-ready proposal.

## Migration Context Shape

The context builder SHOULD produce JSON strings for prompt interpolation:

```python
MigrationContext(
    old_index_version=active_threshold_index_version,
    new_index_version=latest_aa_index_version,
    old_distribution=metric_distribution(version=old),
    new_distribution=metric_distribution(version=new),
    roles=[
        {
            "role_id": role.id,
            "current_metric": active_threshold.metric,
            "current_threshold": active_threshold.threshold_value,
            "criticality": role.criticality,
            "minimum_combo_size": config.minimum_combo_size,
            "minimum_context": role.requirements.minimum_context,
            "required_capabilities": role.requirements.capabilities,
            "protected_demand": demand_summary.get(role.id),
        }
    ],
    capacity_summary={
        role_id: {
            metric: [
                {
                    "threshold": candidate_threshold,
                    "eligible_endpoints": count,
                    "independent_quota_pools": count,
                    "provider_groups": count,
                    "all_free_confirmed": True,
                    "all_context_ok": True,
                    "all_capabilities_ok": True,
                    "all_live_quota_ok": True,
                }
            ]
        }
    },
    percentile_mapping={
        role_id: {
            "old_percentile": percentile_of_old_threshold,
            "new_same_percentile_threshold": threshold_at_new_percentile,
        }
    },
)
```

## Proposal Schema

```python
class RoleThresholdProposal(BaseModel):
    metric: Literal["intelligence_index", "coding_index", "agentic_index"]
    threshold_value: float
    rationale: str | None = None

class MigrationProposalResponse(BaseModel):
    index_version: str
    roles: dict[str, RoleThresholdProposal] = Field(default_factory=dict)
```

Only `index_version`, `roles[*].metric`, and `roles[*].threshold_value` are
machine-used. `rationale` is optional audit text only. The implementation SHALL
NOT require `summary`, `warnings`, or `confidence` unless a later approved slice
wires those fields into operator review or deterministic policy. The
implementation MAY accept legacy `threshold` only inside test fixtures during the
migration slice, but production persistence SHALL normalize to `threshold_value`
and SHALL NOT keep backwards compatibility after the slice finishes.

## Validation Pseudocode

```python
def validate_migration_proposal(proposal, context, repository_state):
    errors = []
    if proposal.index_version != context.new_index_version:
        errors.append("wrong_index_version")

    for role_id, policy in proposal.roles.items():
        role = context.roles.get(role_id)
        if role is None:
            errors.append(f"{role_id}:unknown_role")
            continue

        eligible = find_eligible_endpoints(
            metric=policy.metric,
            threshold=policy.threshold_value,
            required_capabilities=role.required_capabilities,
            minimum_context=role.minimum_context,
            free_only=True,
            confirmed_access_only=True,
            healthy_only=True,
            live_quota_only=True,
        )

        if not threshold_exists(policy.metric, policy.threshold_value, context.new_distribution):
            errors.append(f"{role_id}:threshold_outside_new_scale")
        if len(eligible) < role.minimum_combo_size:
            errors.append(f"{role_id}:insufficient_combo_size")
        if independent_quota_pool_count(eligible) < role.minimum_independent_pools:
            errors.append(f"{role_id}:insufficient_independent_quota")
        if provider_group_count(eligible) < role.minimum_provider_groups:
            errors.append(f"{role_id}:insufficient_provider_diversity")
        if protected_capacity(eligible) < role.protected_demand:
            errors.append(f"{role_id}:protected_demand_not_covered")
        if any(endpoint.is_paid or not endpoint.confirmed_free for endpoint in eligible):
            errors.append(f"{role_id}:paid_or_unconfirmed_endpoint")

    if errors:
        raise MigrationValidationError(errors)
```

## Analyze Pseudocode

```python
def run_aa_index_proposal(repository, llm_runtime, config):
    context = build_migration_context(repository, config)
    if context.latest_aa_snapshot_missing:
        return error("aa_unavailable")

    proposal_result = run_migration_agent(
        llm_runtime,
        context=context,
        prompt_path=config.prompts_dir / "aa-index-migration.md",
        repair_attempts=3,
    )

    if proposal_result.status == "advisory_unavailable":
        return error("advisory_unavailable")

    validation = validate_migration_proposal(proposal_result.proposal, context, repository.current_state())
    if validation.errors:
        repaired = repair_until_valid_or_manual_review(...)
        if not repaired.valid:
            return error("migration_needs_manual_review")

    persist_migration(
        status="proposed",
        baseline_snapshot_json=context.audit_snapshot,
        threshold_proposal_json=normalized_valid_proposal,
        llm_proposal_json=raw_llm_attempts_and_validation_report,
    )
```

## Rollout Pseudocode

```python
def rollout_latest_aa_migration(repository):
    migration = latest(status="approved")
    context = rebuild_context_from_baseline(migration.baseline_snapshot_json)
    proposal = parse(migration.threshold_proposal_json)
    validate_migration_proposal(proposal, context, repository.current_state())
    dry_run_threshold_rollout(proposal)
    apply_threshold_versions(proposal)
    mark_rolled_out()
```

## Risks

- Context can exceed prompt limits. Mitigation: summarize distributions and
  capacity bands; store full audit snapshot in DB, not prompt.
- Live quota may drift between analyze and rollout. Mitigation: validate at both
  points and fail rollout if current state no longer satisfies the proposal.
- Repair loop could hide deterministic failures. Mitigation: persist compact
  attempt reports and stop after three attempts with manual-review status.
