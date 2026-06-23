from __future__ import annotations

from fmo.pipeline import PipelineContext, StageResult

from . import _legacy
from ._legacy import StageDependencies


def _probing_stage(dependencies: StageDependencies, context: PipelineContext) -> StageResult:
    return _legacy._probing_stage(dependencies, context)
