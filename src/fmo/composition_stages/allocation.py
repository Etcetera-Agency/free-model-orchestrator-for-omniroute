from __future__ import annotations

from fmo.pipeline import PipelineContext, StageResult

from . import _legacy
from ._legacy import StageDependencies


def _demand_forecast_stage(_dependencies: StageDependencies, context: PipelineContext) -> StageResult:
    return _legacy._demand_forecast_stage(_dependencies, context)


def _allocation_stage(_dependencies: StageDependencies, context: PipelineContext) -> StageResult:
    return _legacy._allocation_stage(_dependencies, context)


def _configured_router_input(model_id: str) -> tuple[str, ...]:
    return _legacy._configured_router_input(model_id)
