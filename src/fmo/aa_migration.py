from dataclasses import dataclass


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
    return instructor_call(selected_model)


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
