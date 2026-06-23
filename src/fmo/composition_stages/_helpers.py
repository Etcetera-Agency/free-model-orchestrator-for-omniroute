from __future__ import annotations

from collections.abc import Callable

from fmo.pipeline import PipelineContext, StageResult

from ._base import StageAdapter, StageAdapters, StageDependencies


def _effect_result(stage_name: str, *, changed: bool) -> StageResult:
    effect = "repository_write" if changed else "idempotent_no_change"
    return StageResult(
        status="success",
        changed=changed,
        idempotency_key=f"{stage_name}:production",
        details={"adapter": stage_name, "effect": effect},
    )


def _not_implemented_stage(name: str) -> StageAdapter:
    def run(_dependencies: StageDependencies, _context: PipelineContext) -> StageResult:
        return StageResult(
            status="not_implemented",
            idempotency_key=f"{name}:not-implemented",
            reason=f"{name} adapter is not wired",
            details={"adapter": name, "effect": None},
        )

    return run


def _adapter_stage(
    name: str,
    dependencies: StageDependencies,
    adapters: StageAdapters,
) -> Callable[[PipelineContext], StageResult]:
    adapter = adapters.stage_adapters.get(name, _not_implemented_stage(name))

    def run(context: PipelineContext) -> StageResult:
        return adapter(dependencies, context)

    return run


def _omniroute_instance_id(dependencies: StageDependencies) -> str:
    if dependencies.config is None:
        return "default"
    return dependencies.config.omniroute_url
