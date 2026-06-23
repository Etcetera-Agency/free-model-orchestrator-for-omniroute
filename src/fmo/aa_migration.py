import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from fmo.llm_runtime import LlmSiteConfig, complete_with_adapter

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "reference" / "prompts"
AA_INDEX_MIGRATION_PROMPT = PROMPTS_DIR / "aa-index-migration.md"
ALLOWED_METRICS = {"intelligence_index", "coding_index", "agentic_index"}


@dataclass(frozen=True)
class MigrationRecord:
    created: bool
    freeze_thresholds: bool
    current_combos: dict[str, list[str]]
    production_recalculation_stopped: bool


@dataclass(frozen=True)
class MigrationValidation:
    can_rollout: bool
    needs_approval: bool
    errors: list[str] = field(default_factory=list)


class RoleThresholdProposal(BaseModel):
    metric: Literal["intelligence_index", "coding_index", "agentic_index"]
    threshold_value: float
    rationale: str | None = None


class MigrationProposalResponse(BaseModel):
    index_version: str
    roles: dict[str, RoleThresholdProposal] = Field(default_factory=dict)


def detect_index_change(
    *,
    active_version: str,
    fetched_version: str,
    thresholds: dict,  # noqa: ARG001 - reserved interface param
    combos: dict[str, list[str]],
) -> MigrationRecord:
    changed = active_version != fetched_version
    return MigrationRecord(
        created=changed,
        freeze_thresholds=changed,
        current_combos=combos,
        production_recalculation_stopped=changed,
    )


def select_migration_model(candidates: list[dict]) -> dict | None:
    available = [candidate for candidate in candidates if candidate.get("available")]
    if not available:
        return None
    return max(available, key=lambda candidate: candidate.get("intelligence_index", 0))


def run_migration_agent(
    instructor_call,
    migration_context: dict[str, Any] | None,
    *,
    repair_errors: list[str] | None = None,
) -> dict:
    if migration_context is None:
        return {"status": "waiting_for_model"}
    try:
        site = LlmSiteConfig(
            name="aa-index-migration",
            model=None if hasattr(instructor_call, "complete") else "omniroute/free-migration",
            prompt_path=AA_INDEX_MIGRATION_PROMPT,
            max_prompt_chars=4000,
            advisory=True,
        )
        context = _prompt_context(migration_context, repair_errors=repair_errors or [])
        if hasattr(instructor_call, "complete"):
            proposal = instructor_call.complete(site=site, context=context, response_model=MigrationProposalResponse)
        else:
            proposal = complete_with_adapter(
                instructor_call,
                site=site,
                context=context,
                response_model=MigrationProposalResponse,
            )
    except Exception:
        return {"status": "advisory_unavailable"}
    return proposal.model_dump()


def validate_migration_proposal(
    proposal: dict, *, new_version: str, role_capacity: dict[str, dict], approved: bool
) -> MigrationValidation:
    errors = migration_validation_errors(proposal, new_version=new_version, role_capacity=role_capacity)
    if errors:
        raise ValueError(",".join(errors))
    return MigrationValidation(can_rollout=approved, needs_approval=not approved, errors=[])


def migration_validation_errors(proposal: dict, *, new_version: str, role_capacity: dict[str, dict]) -> list[str]:
    # AICODE-NOTE: Migration advice is never trusted directly; this validator
    # emits compact repair/rollout blocker codes used by analyze and rollout.
    errors = []
    if proposal.get("index_version") != new_version:
        errors.append("wrong_index_version")
    for role, policy in proposal.get("roles", {}).items():
        capacity = role_capacity.get(role)
        if capacity is None:
            errors.append(f"{role}:unknown_role")
            continue
        metric = policy.get("metric")
        threshold = policy.get("threshold_value")
        if metric not in ALLOWED_METRICS:
            errors.append(f"{role}:invalid_metric")
        if not isinstance(threshold, int | float):
            errors.append(f"{role}:threshold_missing")
        elif threshold < capacity.get("min_threshold", 0) or threshold > capacity.get("max_threshold", 100):
            errors.append(f"{role}:threshold_outside_new_scale")
        if capacity.get("eligible", 0) < capacity.get("minimum", 1):
            errors.append(f"{role}:insufficient_combo_size")
        if capacity.get("independent_quota_pools", 0) < capacity.get("minimum_independent_pools", 0):
            errors.append(f"{role}:insufficient_independent_quota")
        if capacity.get("provider_groups", 0) < capacity.get("minimum_provider_groups", 0):
            errors.append(f"{role}:insufficient_provider_diversity")
        if not capacity.get("quota_ok"):
            errors.append(f"{role}:quota_not_ok")
        if not capacity.get("quality_ok"):
            errors.append(f"{role}:quality_not_ok")
        for flag, code in (
            ("context_ok", "missing_context"),
            ("capabilities_ok", "missing_capability"),
            ("free_confirmed", "paid_or_unconfirmed_endpoint"),
            ("healthy", "unhealthy_endpoint"),
            ("live_quota_ok", "exhausted_live_quota"),
        ):
            if capacity.get(flag, True) is not True:
                errors.append(f"{role}:{code}")
    return errors


def _prompt_context(migration_context: dict[str, Any], *, repair_errors: list[str]) -> dict[str, str]:
    context = {
        "old_index_version": str(migration_context.get("old_index_version") or "unknown"),
        "new_index_version": str(migration_context.get("new_index_version") or "unknown"),
        "old_distribution": json.dumps(migration_context.get("old_distribution", {}), sort_keys=True),
        "new_distribution": json.dumps(migration_context.get("new_distribution", {}), sort_keys=True),
        "roles": json.dumps(migration_context.get("roles", []), sort_keys=True),
        "capacity_summary": json.dumps(migration_context.get("capacity_summary", {}), sort_keys=True),
        "percentile_mapping": json.dumps(migration_context.get("percentile_mapping", {}), sort_keys=True),
    }
    if repair_errors:
        context["repair_errors"] = json.dumps(repair_errors, sort_keys=True)
    return context
