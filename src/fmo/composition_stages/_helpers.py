from __future__ import annotations

from collections.abc import Callable

from fmo.idempotency import canonical_slug, hash_parts
from fmo.pipeline import PipelineContext, StageResult
from fmo.quota_normalize import quota_limit, quota_metric, remaining_amount

from ._base import StageAdapter, StageAdapters, StageDependencies

_canonical_slug = canonical_slug
_hash_parts = hash_parts
_quota_metric = quota_metric
_quota_limit = quota_limit
_remaining_amount = remaining_amount


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
