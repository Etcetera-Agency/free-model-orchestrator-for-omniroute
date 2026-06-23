from __future__ import annotations

from typing import Any

from fmo.pipeline import PipelineContext, StageResult

from . import _legacy
from ._legacy import StageDependencies


def _rollback_stage(dependencies: StageDependencies, context: PipelineContext) -> StageResult:
    return _legacy._rollback_stage(dependencies, context)


def _rollback_targets(transaction: Any, config: dict[str, Any]) -> list[Any] | None:
    return _legacy._rollback_targets(transaction, config)


def _rollback_combo_id(*, endpoint: str | None, role: str | None) -> str | None:
    return _legacy._rollback_combo_id(endpoint=endpoint, role=role)
