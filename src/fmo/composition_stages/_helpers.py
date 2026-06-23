from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fmo.pipeline import PipelineContext, StageResult

from . import _legacy
from ._legacy import StageAdapter, StageDependencies


def _effect_result(stage_name: str, *, changed: bool) -> StageResult:
    return _legacy._effect_result(stage_name, changed=changed)


def _canonical_slug(provider_model_id: str) -> str:
    return _legacy._canonical_slug(provider_model_id)


def _hash_parts(*parts: str) -> str:
    return _legacy._hash_parts(*parts)


def _quota_metric(limits: Any) -> tuple[str, float]:
    return _legacy._quota_metric(limits)


def _quota_limit(limits: Any) -> float:
    return _legacy._quota_limit(limits)


def _remaining_amount(effective_remaining: Any) -> float:
    return _legacy._remaining_amount(effective_remaining)


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
