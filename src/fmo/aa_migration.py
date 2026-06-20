import json
from dataclasses import dataclass

from pydantic import BaseModel, Field

from fmo.llm_runtime import LlmSiteConfig, complete_with_adapter


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


class MigrationProposalResponse(BaseModel):
    index_version: str
    roles: dict[str, dict] = Field(default_factory=dict)


def detect_index_change(*, active_version: str, fetched_version: str, thresholds: dict, combos: dict[str, list[str]]) -> MigrationRecord:
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


def run_migration_agent(instructor_call, selected_model: dict | None) -> dict:
    if selected_model is None:
        return {"status": "waiting_for_model"}
    try:
        site = LlmSiteConfig(
            name="aa-index-migration",
            model=selected_model.get("endpoint", "omniroute/free-migration"),
            max_prompt_chars=4000,
            advisory=True,
        )
        context = {"prompt": json.dumps(selected_model, sort_keys=True)}
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


def validate_migration_proposal(proposal: dict, *, new_version: str, role_capacity: dict[str, dict], approved: bool) -> MigrationValidation:
    if proposal.get("index_version") != new_version:
        raise ValueError("wrong_index_version")
    for role, policy in proposal.get("roles", {}).items():
        if policy.get("metric") not in {"intelligence_index", "coding_index", "agentic_index"}:
            raise ValueError("invalid_metric")
        capacity = role_capacity.get(role, {})
        if capacity.get("eligible", 0) < capacity.get("minimum", 1):
            raise ValueError("insufficient_combo_size")
        if not capacity.get("quota_ok") or not capacity.get("quality_ok"):
            raise ValueError("operational_validation_failed")
    return MigrationValidation(can_rollout=approved, needs_approval=not approved)
