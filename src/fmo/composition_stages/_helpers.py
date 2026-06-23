from __future__ import annotations

from collections.abc import Callable

from fmo.idempotency import canonical_slug, hash_parts
from fmo.pipeline import PipelineContext, StageResult
from fmo.quota_normalize import quota_limit, quota_metric, remaining_amount

from . import _legacy
from ._legacy import StageAdapter, StageDependencies

_canonical_slug = canonical_slug
_hash_parts = hash_parts
_quota_metric = quota_metric
_quota_limit = quota_limit
_remaining_amount = remaining_amount


def _effect_result(stage_name: str, *, changed: bool) -> StageResult:
    return _legacy._effect_result(stage_name, changed=changed)


def _not_implemented_stage(name: str) -> StageAdapter:
    return _legacy._not_implemented_stage(name)


def _adapter_stage(
    name: str,
    dependencies: StageDependencies,
    adapters: _legacy.StageAdapters,
) -> Callable[[PipelineContext], StageResult]:
    return _legacy._adapter_stage(name, dependencies, adapters)


def _omniroute_instance_id(dependencies: StageDependencies) -> str:
    return _legacy._omniroute_instance_id(dependencies)
