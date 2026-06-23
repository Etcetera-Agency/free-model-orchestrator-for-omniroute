from __future__ import annotations

from typing import Any

from fmo.pipeline import PipelineContext, StageResult

from . import _legacy
from ._legacy import StageDependencies


def _access_classification_stage(_dependencies: StageDependencies, context: PipelineContext) -> StageResult:
    return _legacy._access_classification_stage(_dependencies, context)


def _record_lost_free_access_state(transaction: Any, endpoint_id: Any) -> None:
    _legacy._record_lost_free_access_state(transaction, endpoint_id)


def _canonical_access_status(status: str) -> str:
    return _legacy._canonical_access_status(status)
