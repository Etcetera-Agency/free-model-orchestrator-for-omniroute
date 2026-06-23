from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from fmo.pipeline import PipelineContext, StageResult
from fmo.smart_review import ComboReviewResult

from . import _legacy
from ._legacy import StageDependencies


def _diff_stage(dependencies: StageDependencies, context: PipelineContext) -> StageResult:
    return _legacy._diff_stage(dependencies, context)


def _review_diff(dependencies: StageDependencies, diff: dict[str, Any]) -> ComboReviewResult:
    return _legacy._review_diff(dependencies, diff)


def _review_payload(review: ComboReviewResult) -> dict[str, Any]:
    return _legacy._review_payload(review)


def _apply_stage(dependencies: StageDependencies, context: PipelineContext) -> StageResult:
    return _legacy._apply_stage(dependencies, context)


def _persist_applied_snapshot(context: PipelineContext, diff: Any, before: list[str], desired: list[str]) -> None:
    _legacy._persist_applied_snapshot(context, diff, before, desired)


def _rollback_apply_mutations(
    client: Any, applied: Sequence[tuple[Any, list[str], list[str]]], *, failed: tuple[str, list[str]]
) -> bool:
    return _legacy._rollback_apply_mutations(client, applied, failed=failed)


def _combo_models_idempotency_key(combo_id: str, models: Sequence[str]) -> str:
    return _legacy._combo_models_idempotency_key(combo_id, models)


def _delete_applied_snapshots_for_run(
    context: PipelineContext, applied: Sequence[tuple[Any, list[str], list[str]]]
) -> None:
    _legacy._delete_applied_snapshots_for_run(context, applied)


def _derive_apply_stage_safety(
    transaction: Any, diffs: Sequence[Any], *, minimum_safety_buffer: float, minimum_percent_remaining: float
) -> dict[str, bool]:
    return _legacy._derive_apply_stage_safety(
        transaction,
        diffs,
        minimum_safety_buffer=minimum_safety_buffer,
        minimum_percent_remaining=minimum_percent_remaining,
    )


def _desired_apply_endpoint_ids(diffs: Sequence[Any]) -> list[str]:
    return _legacy._desired_apply_endpoint_ids(diffs)


def _desired_endpoints_have_current_quota_safety(
    transaction: Any, endpoint_ids: Sequence[str], *, minimum_safety_buffer: float, minimum_percent_remaining: float
) -> bool:
    return _legacy._desired_endpoints_have_current_quota_safety(
        transaction,
        endpoint_ids,
        minimum_safety_buffer=minimum_safety_buffer,
        minimum_percent_remaining=minimum_percent_remaining,
    )


def _endpoint_quota_row_is_safe(
    row: Any, *, now: datetime, oldest_allowed: datetime, minimum_safety_buffer: float, minimum_percent_remaining: float
) -> bool:
    return _legacy._endpoint_quota_row_is_safe(
        row,
        now=now,
        oldest_allowed=oldest_allowed,
        minimum_safety_buffer=minimum_safety_buffer,
        minimum_percent_remaining=minimum_percent_remaining,
    )


def _desired_endpoints_have_current_probe_success(transaction: Any, endpoint_ids: Sequence[str]) -> bool:
    return _legacy._desired_endpoints_have_current_probe_success(transaction, endpoint_ids)


def _read_current_combos(client: Any) -> dict[str, list[str]]:
    return _legacy._read_current_combos(client)


def _smoke_combo(client: Any, combo_id: str) -> bool:
    return _legacy._smoke_combo(client, combo_id)
