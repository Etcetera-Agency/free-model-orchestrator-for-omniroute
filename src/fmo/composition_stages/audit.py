from __future__ import annotations

from fmo.pipeline import PipelineContext, StageResult

from ._base import StageDependencies
from ._helpers import _effect_result


def _audit_stage(_dependencies: StageDependencies, _context: PipelineContext) -> StageResult:
    return _effect_result("audit", changed=False)
