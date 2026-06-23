from __future__ import annotations

from typing import Any

from fmo.pipeline import PipelineContext, StageResult

from . import _legacy
from ._legacy import StageDependencies


def _quota_research_stage(dependencies: StageDependencies, context: PipelineContext) -> StageResult:
    return _legacy._quota_research_stage(dependencies, context)


def _quota_sync_stage(dependencies: StageDependencies, context: PipelineContext) -> StageResult:
    return _legacy._quota_sync_stage(dependencies, context)


def _ensure_quota_pool(transaction: Any, provider_id: str, connection_id: str, account_id: Any) -> Any:
    return _legacy._ensure_quota_pool(transaction, provider_id, connection_id, account_id)


def _ensure_named_quota_pool(transaction: Any, provider_id: str, pool_key: str) -> Any:
    return _legacy._ensure_named_quota_pool(transaction, provider_id, pool_key)
