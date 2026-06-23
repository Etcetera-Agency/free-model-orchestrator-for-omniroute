from __future__ import annotations

from . import _legacy
from ._legacy import *  # noqa: F403
from ._legacy import (
    _adapter_stage as _adapter_stage,
)
from ._legacy import (
    _latest_role_diagnostic as _latest_role_diagnostic,
)
from ._legacy import (
    _read_current_combos as _read_current_combos,
)
from ._legacy import (
    _rollback_stage as _rollback_stage,
)
from ._legacy import (
    _smoke_combo as _smoke_combo,
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

_legacy_production_stage_adapters = _legacy._production_stage_adapters


def _production_stage_adapters() -> dict[str, _legacy.StageAdapter]:
    adapters = dict(_legacy_production_stage_adapters())
    adapters["model-matching"] = _model_matching_stage
    adapters["quota-research"] = _quota_research_stage
    adapters["access-classification"] = _access_classification_stage
    adapters["quota-sync"] = _quota_sync_stage
    return adapters


# AICODE-NOTE: keep the package shim import-stable while stage clusters move
# out of _legacy across the staged refactor slices.
_legacy._production_stage_adapters = _production_stage_adapters
