from __future__ import annotations

from fmo.idempotency import utcnow
from fmo.pipeline import PipelineContext, StageResult
from fmo.telemetry import sync_live_telemetry

from ._helpers import _effect_result
from ._legacy import StageDependencies
from .roles import _insert_health_observation


def _telemetry_sync_stage(dependencies: StageDependencies, context: PipelineContext) -> StageResult:
    if dependencies.omniroute_client is None:
        return StageResult(status="external_dependency_failed", reason="omniroute_client_required")
    snapshot = sync_live_telemetry(dependencies.omniroute_client)
    if snapshot.errors:
        return StageResult(status="external_dependency_failed", reason=snapshot.errors[0].reason)
    observed_at = utcnow()
    written = 0
    with context.repository.database.transaction() as transaction:
        for provider_id, metric in snapshot.provider_metrics.items():
            provider = transaction.execute(
                "SELECT id FROM providers WHERE omniroute_provider_id = %(provider_id)s LIMIT 1",
                {"provider_id": provider_id},
            ).fetchone()
            if provider is None:
                continue
            _insert_health_observation(
                transaction,
                provider_id=provider["id"],
                endpoint_id=None,
                status="active",
                metric=metric,
                observed_at=observed_at,
            )
            written += 1
        for (provider_id, model_id), metric in snapshot.model_metrics.items():
            endpoint = transaction.execute(
                """
                SELECT pe.id
                FROM provider_endpoints pe
                JOIN provider_accounts pa ON pa.id = pe.provider_account_id
                JOIN providers p ON p.id = pa.provider_id
                WHERE p.omniroute_provider_id = %(provider_id)s
                  AND pe.provider_model_id = %(model_id)s
                LIMIT 1
                """,
                {"provider_id": provider_id, "model_id": model_id},
            ).fetchone()
            if endpoint is None:
                continue
            _insert_health_observation(
                transaction,
                provider_id=None,
                endpoint_id=endpoint["id"],
                status="active" if metric.failure_count == 0 else "degraded",
                metric=metric,
                observed_at=observed_at,
            )
            written += 1
    return _effect_result("telemetry-sync", changed=written > 0)
