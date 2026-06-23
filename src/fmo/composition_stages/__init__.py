from __future__ import annotations

from . import _legacy
from ._helpers import _adapter_stage as _adapter_stage
from ._helpers import _canonical_slug as _canonical_slug
from ._helpers import _effect_result as _effect_result
from ._helpers import _hash_parts as _hash_parts
from ._helpers import _not_implemented_stage as _not_implemented_stage
from ._helpers import _omniroute_instance_id as _omniroute_instance_id
from ._helpers import _quota_limit as _quota_limit
from ._helpers import _quota_metric as _quota_metric
from ._helpers import _remaining_amount as _remaining_amount
from ._legacy import *  # noqa: F403
from ._legacy import (
    _latest_role_diagnostic as _latest_role_diagnostic,
)
from .access import (
    _access_classification_stage as _access_classification_stage,
)
from .access import (
    _canonical_access_status as _canonical_access_status,
)
from .access import (
    _record_lost_free_access_state as _record_lost_free_access_state,
)
from .allocation import _allocation_stage as _allocation_stage
from .allocation import _configured_router_input as _configured_router_input
from .allocation import _demand_forecast_stage as _demand_forecast_stage
from .apply import _apply_stage as _apply_stage
from .apply import _combo_models_idempotency_key as _combo_models_idempotency_key
from .apply import _delete_applied_snapshots_for_run as _delete_applied_snapshots_for_run
from .apply import _derive_apply_stage_safety as _derive_apply_stage_safety
from .apply import _desired_apply_endpoint_ids as _desired_apply_endpoint_ids
from .apply import _desired_endpoints_have_current_probe_success as _desired_endpoints_have_current_probe_success
from .apply import _desired_endpoints_have_current_quota_safety as _desired_endpoints_have_current_quota_safety
from .apply import _diff_stage as _diff_stage
from .apply import _endpoint_quota_row_is_safe as _endpoint_quota_row_is_safe
from .apply import _persist_applied_snapshot as _persist_applied_snapshot
from .apply import _read_current_combos as _read_current_combos
from .apply import _review_diff as _review_diff
from .apply import _review_payload as _review_payload
from .apply import _rollback_apply_mutations as _rollback_apply_mutations
from .apply import _smoke_combo as _smoke_combo
from .audit import _audit_stage as _audit_stage
from .discovery import (
    _account_discovery_stage as _account_discovery_stage,
)
from .discovery import (
    _free_candidate_stage as _free_candidate_stage,
)
from .discovery import (
    _metadata_stage as _metadata_stage,
)
from .discovery import (
    _model_matching_stage as _model_matching_stage,
)
from .discovery import (
    _scan_catalogs as _scan_catalogs,
)
from .inventory import _hermes_inventory_stage as _hermes_inventory_stage
from .inventory import _read_hermes_inventory as _read_hermes_inventory
from .inventory import _run_hermes_inspector as _run_hermes_inspector
from .probing import _probing_stage as _probing_stage
from .quota import (
    _ensure_named_quota_pool as _ensure_named_quota_pool,
)
from .quota import (
    _ensure_quota_pool as _ensure_quota_pool,
)
from .quota import (
    _quota_research_stage as _quota_research_stage,
)
from .quota import (
    _quota_sync_stage as _quota_sync_stage,
)
from .roles import _context_window_eligibility as _context_window_eligibility
from .roles import _health_component as _health_component
from .roles import _insert_health_observation as _insert_health_observation
from .roles import _latency_component as _latency_component
from .roles import _latest_aa_metrics_by_model as _latest_aa_metrics_by_model
from .roles import _latest_health_by_endpoint as _latest_health_by_endpoint
from .roles import _latest_protected_requests as _latest_protected_requests
from .roles import _latest_remaining_by_pool as _latest_remaining_by_pool
from .roles import _quality_band_candidates as _quality_band_candidates
from .roles import _quality_gate_eligibility as _quality_gate_eligibility
from .roles import _role_lifecycle_stage as _role_lifecycle_stage
from .roles import _role_scoring_stage as _role_scoring_stage
from .roles import _roles_needing_quality_recalibration as _roles_needing_quality_recalibration
from .roles import _seed_quality_bands as _seed_quality_bands
from .roles import _stability_component as _stability_component
from .rollback import _rollback_combo_id as _rollback_combo_id
from .rollback import _rollback_stage as _rollback_stage
from .rollback import _rollback_targets as _rollback_targets
from .telemetry import _telemetry_sync_stage as _telemetry_sync_stage

_legacy_production_stage_adapters = _legacy._production_stage_adapters


def _production_stage_adapters() -> dict[str, _legacy.StageAdapter]:
    adapters = dict(_legacy_production_stage_adapters())
    adapters["model-matching"] = _model_matching_stage
    adapters["quota-research"] = _quota_research_stage
    adapters["access-classification"] = _access_classification_stage
    adapters["quota-sync"] = _quota_sync_stage
    adapters["probing"] = _probing_stage
    adapters["telemetry-sync"] = _telemetry_sync_stage
    adapters["hermes-inventory"] = _hermes_inventory_stage
    adapters["role-lifecycle"] = _role_lifecycle_stage
    adapters["role-scoring"] = _role_scoring_stage
    adapters["demand-forecast"] = _demand_forecast_stage
    adapters["allocation"] = _allocation_stage
    adapters["diff"] = _diff_stage
    adapters["apply"] = _apply_stage
    adapters["audit"] = _audit_stage
    return adapters


# AICODE-NOTE: keep the package shim import-stable while stage clusters move
# out of _legacy across the staged refactor slices.
_legacy._production_stage_adapters = _production_stage_adapters
