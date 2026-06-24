from __future__ import annotations

from fmo.idempotency import hash_parts, utcnow
from fmo.omniroute import OmniRouteRequestError
from fmo.pipeline import PipelineContext, StageResult
from fmo.probes import handle_probe_error, probe_endpoint, probe_suites
from fmo.quota_normalize import remaining_amount

from ._base import StageDependencies
from ._helpers import _effect_result
from .apply import _read_current_combos

PROBE_SUITE_VERSION = "production-v2-stream"


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
              AND pe.removed_at IS NULL
              AND p.enabled = true
              AND pa.enabled = true
            ORDER BY pe.provider_model_id
            """
        ).fetchall()
    seed_models = _current_combo_seed_models(dependencies.omniroute_client)
    if seed_models:
        seed_rows = [row for row in rows if row["provider_model_id"] in seed_models]
        if seed_rows:
            # AICODE-NOTE: Provider-wide quota rules can confirm hundreds of
            # endpoints; probe live one-member combo seeds first to avoid
            # blasting providers with unavailable catalog entries.
            rows = seed_rows
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
        request_hash = hash_parts(str(row["id"]), started_at.date().isoformat(), PROBE_SUITE_VERSION, "basic")
        with context.repository.database.transaction() as transaction:
            probe = context.repository.probes.record(
                transaction,
                endpoint_id=row["id"],
                suite_version=PROBE_SUITE_VERSION,
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
                {"status": "passed" if probe["passed"] else "failed", "endpoint_id": row["id"]},
            )
        written += 1
    return _effect_result("probing", changed=written > 0)


def _current_combo_seed_models(client) -> set[str]:
    current = _read_current_combos(client)
    models: set[str] = set()
    for combo_id, members in current.items():
        if not combo_id.startswith("fmo-") or len(members) != 1:
            continue
        member = members[0]
        if isinstance(member, dict) and member.get("model"):
            models.add(str(member["model"]))
        elif isinstance(member, str):
            models.add(member)
    return models
