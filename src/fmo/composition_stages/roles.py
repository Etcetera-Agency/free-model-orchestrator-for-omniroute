from __future__ import annotations

from typing import Any

from fmo.pipeline import PipelineContext, StageResult
from fmo.scoring import EligibilityDecision

from . import _legacy
from ._legacy import StageDependencies


def _role_lifecycle_stage(_dependencies: StageDependencies, context: PipelineContext) -> StageResult:
    return _legacy._role_lifecycle_stage(_dependencies, context)


def _role_scoring_stage(_dependencies: StageDependencies, context: PipelineContext) -> StageResult:
    return _legacy._role_scoring_stage(_dependencies, context)


def _seed_quality_bands(transaction: Any, client: Any) -> None:
    _legacy._seed_quality_bands(transaction, client)


def _quality_band_candidates(transaction: Any, metric: str) -> list[dict[str, Any]]:
    return _legacy._quality_band_candidates(transaction, metric)


def _latest_protected_requests(transaction: Any, role_id: str) -> float:
    return _legacy._latest_protected_requests(transaction, role_id)


def _latest_aa_metrics_by_model(transaction: Any) -> dict[Any, dict[str, Any]]:
    return _legacy._latest_aa_metrics_by_model(transaction)


def _latest_health_by_endpoint(transaction: Any) -> dict[str, dict[str, float | int | None]]:
    return _legacy._latest_health_by_endpoint(transaction)


def _latest_remaining_by_pool(transaction: Any) -> dict[str, float]:
    return _legacy._latest_remaining_by_pool(transaction)


def _health_component(status: str | None, success_rate: float | None, error_rate: float | None) -> float:
    return _legacy._health_component(status, success_rate, error_rate)


def _stability_component(status: str | None, sample_count: int | None) -> float:
    return _legacy._stability_component(status, sample_count)


def _latency_component(source: str, value: float | None) -> float:
    return _legacy._latency_component(source, value)


def _context_window_eligibility(endpoint: Any, requirements: dict[str, Any]) -> EligibilityDecision:
    return _legacy._context_window_eligibility(endpoint, requirements)


def _quality_gate_eligibility(
    role: Any, metrics_row: dict[str, Any] | None, requirements: dict[str, Any]
) -> EligibilityDecision:
    return _legacy._quality_gate_eligibility(role, metrics_row, requirements)


def _roles_needing_quality_recalibration(transaction: Any) -> set[str]:
    return _legacy._roles_needing_quality_recalibration(transaction)


def _insert_health_observation(
    transaction: Any,
    *,
    provider_id: Any | None,
    endpoint_id: Any | None,
    status: str,
    metric: Any,
    observed_at: Any,
) -> None:
    _legacy._insert_health_observation(
        transaction,
        provider_id=provider_id,
        endpoint_id=endpoint_id,
        status=status,
        metric=metric,
        observed_at=observed_at,
    )
