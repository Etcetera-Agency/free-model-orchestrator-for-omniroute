from __future__ import annotations

from fmo.pipeline import PipelineContext, StageResult

from . import _legacy
from ._legacy import StageDependencies


def _telemetry_sync_stage(dependencies: StageDependencies, context: PipelineContext) -> StageResult:
    return _legacy._telemetry_sync_stage(dependencies, context)
