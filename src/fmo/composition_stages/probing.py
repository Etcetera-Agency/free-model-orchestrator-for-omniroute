from __future__ import annotations

from fmo.idempotency import hash_parts, utcnow
from fmo.omniroute import OmniRouteRequestError
from fmo.pipeline import PipelineContext, StageResult
from fmo.probes import handle_probe_error, probe_endpoint, probe_suites
from fmo.quota_normalize import remaining_amount

from ._base import StageDependencies
from ._helpers import _effect_result


def _probing_stage(dependencies: StageDependencies, context: PipelineContext) -> StageResult:
    if dependencies.omniroute_client is None:
        return StageResult(status="external_dependency_failed", reason="omniroute_client_required")
    with context.repository.database.transaction() as transaction:
        rows = transaction.execute(
            """
            SELECT pe.id, pe.provider_model_id, pe.capabilities, p.omniroute_provider_id,
                   eas.status, eas.effective_remaining
            FROM provider_endpoints pe
            JOIN provider_accounts pa ON pa.id = pe.provider_account_id
            JOIN providers p ON p.id = pa.provider_id
            JOIN endpoint_access_states eas ON eas.endpoint_id = pe.id
            WHERE eas.status = 'confirmed'
            ORDER BY pe.provider_model_id
            """
        ).fetchall()
    written = 0
    for row in rows:
        if remaining_amount(row["effective_remaining"]) <= 0:
            continue
        capabilities = dict(row["capabilities"] or {})
        started_at = utcnow()
        http_status = 200
        details = {"suites": list(probe_suites(capabilities)), "reserved_capacity": True}
        try:
            result = probe_endpoint(
                dependencies.omniroute_client,
                provider=row["omniroute_provider_id"],
                model=row["provider_model_id"],
                capabilities=capabilities,
            )
            passed = result.passed
            details["suites"] = list(result.suites)
            if not result.passed:
                http_status = 500
        except OmniRouteRequestError as exc:
            http_status = exc.status_code
            passed = False
            action, reason = handle_probe_error(exc.status_code)
            details.update({"error_action": action, "error_reason": reason})
        finished_at = utcnow()
        request_hash = hash_parts(str(row["id"]), started_at.date().isoformat(), "basic")
        with context.repository.database.transaction() as transaction:
            context.repository.probes.record(
                transaction,
                endpoint_id=row["id"],
                suite_version="production-v1",
                probe_type="basic",
                request_hash=request_hash,
                passed=passed,
                http_status=http_status,
                started_at=started_at,
                finished_at=finished_at,
                details=details,
            )
            transaction.execute(
                "UPDATE provider_endpoints SET probe_status = %(status)s WHERE id = %(endpoint_id)s",
                {"status": "passed" if passed else "failed", "endpoint_id": row["id"]},
            )
        written += 1
    return _effect_result("probing", changed=written > 0)
