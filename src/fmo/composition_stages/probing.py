from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from fmo.idempotency import hash_parts, utcnow
from fmo.omniroute import OmniRouteRequestError
from fmo.pipeline import PipelineContext, StageResult
from fmo.probes import handle_probe_error, probe_suites
from fmo.quota_normalize import remaining_amount
from fmo.scanner import CatalogScanner, scan_live_omniroute_catalogs

from ._base import StageDependencies
from ._helpers import _effect_result, _omniroute_instance_id
from .apply import _read_current_combos

PROBE_SUITE_VERSION = "production-v3-model-test-all"
PROBE_BATCH_SIZE = 100
MODEL_TEST_ALL_PATH = "/api/models/test-all"


@dataclass(frozen=True)
class _ProbeOutcome:
    passed: bool
    http_status: int
    details: dict[str, Any]


def _probing_stage(dependencies: StageDependencies, context: PipelineContext) -> StageResult:
    if dependencies.omniroute_client is None:
        return StageResult(status="external_dependency_failed", reason="omniroute_client_required")
    with context.repository.database.transaction() as transaction:
        rows = transaction.execute(
            """
            SELECT pe.id, pe.provider_model_id, pe.capabilities, p.omniroute_provider_id,
                   pa.omniroute_connection_id, eas.status, eas.effective_remaining
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
    eligible_rows = [
        dict(row)
        for row in rows
        if remaining_amount(row["effective_remaining"]) > 0 and not _is_auto_model(row["provider_model_id"])
    ]
    for batch in _probe_batches(eligible_rows):
        batch_outcomes = _run_model_test_batch(dependencies.omniroute_client, batch)
        for row in batch:
            outcome = batch_outcomes[row["provider_model_id"]]
            written += _record_probe_outcome(context, row=row, outcome=outcome)

    if written > 0:
        # AICODE-NOTE: OmniRoute owns model visibility. After test-all, FMO
        # rereads live catalog instead of parsing which models OmniRoute hid.
        scan_live_omniroute_catalogs(
            CatalogScanner(context.repository),
            dependencies.omniroute_client,
            omniroute_instance_id=_omniroute_instance_id(dependencies),
        )
    return _effect_result("probing", changed=written > 0)


def _probe_batches(rows: Iterable[dict[str, Any]]) -> Iterable[list[dict[str, Any]]]:
    groups: dict[tuple[str, str | None], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[(row["omniroute_provider_id"], row["omniroute_connection_id"])].append(row)
    for batch_rows in groups.values():
        for index in range(0, len(batch_rows), PROBE_BATCH_SIZE):
            yield batch_rows[index : index + PROBE_BATCH_SIZE]


def _is_auto_model(model_id: str) -> bool:
    return model_id.rsplit("/", 1)[-1].endswith("-auto")


def _run_model_test_batch(client: Any, batch: list[dict[str, Any]]) -> dict[str, _ProbeOutcome]:
    provider = batch[0]["omniroute_provider_id"]
    connection_id = batch[0]["omniroute_connection_id"]
    model_ids = [row["provider_model_id"] for row in batch]
    base_details = {
        "omniroute_model_test_all": True,
        "provider": provider,
        "connection_id": connection_id,
        "batch_size": len(batch),
        "respect_rate_limit": True,
        "auto_hide_failed": True,
    }
    payload: dict[str, Any] = {
        "providerId": provider,
        "modelIds": model_ids,
        "respectRateLimit": True,
        "autoHideFailed": True,
    }
    if connection_id:
        payload["connectionId"] = connection_id
    try:
        response = client.post_response(MODEL_TEST_ALL_PATH, payload, headers={"X-OmniRoute-No-Cache": "true"})
    except OmniRouteRequestError as exc:
        action, reason = handle_probe_error(exc.status_code)
        return {
            model_id: _ProbeOutcome(
                passed=False,
                http_status=exc.status_code,
                details={**base_details, "error_action": action, "error_reason": reason},
            )
            for model_id in model_ids
        }
    if response.status_code >= 400:
        return {
            model_id: _ProbeOutcome(
                passed=False,
                http_status=response.status_code,
                details={
                    **base_details,
                    "error_reason": "model_test_all_request_failed",
                    "response_text_sample": response.text[:160],
                },
            )
            for model_id in model_ids
        }

    results = response.body.get("results")
    results = results if isinstance(results, dict) else {}
    return {
        model_id: _outcome_from_batch_entry(
            results.get(model_id),
            base_details={
                **base_details,
                "stopped_early": response.body.get("stoppedEarly") is True,
                "stop_reason": response.body.get("stopReason"),
            },
        )
        for model_id in model_ids
    }


def _outcome_from_batch_entry(entry: Any, *, base_details: dict[str, Any]) -> _ProbeOutcome:
    if not isinstance(entry, dict):
        return _ProbeOutcome(
            passed=False,
            http_status=500,
            details={**base_details, "error_reason": "missing_model_test_result"},
        )
    passed = entry.get("status") == "ok"
    http_status = _entry_http_status(entry, passed=passed)
    details = {
        **base_details,
        "response_status": entry.get("status"),
        "status_code": entry.get("statusCode"),
        "rate_limited": entry.get("rateLimited") is True,
        "retry_after": entry.get("retryAfter"),
        "is_timeout": entry.get("isTimeout") is True,
        "hidden": entry.get("hidden") is True,
    }
    if entry.get("responseText"):
        details["response_text_sample"] = str(entry["responseText"])[:160]
    if not passed:
        details["error_reason"] = _model_test_all_reason(entry)
    return _ProbeOutcome(passed=passed, http_status=http_status, details=details)


def _entry_http_status(entry: dict[str, Any], *, passed: bool) -> int:
    if passed:
        return 200
    if entry.get("rateLimited") is True:
        return 429
    status_code = entry.get("statusCode")
    return status_code if isinstance(status_code, int) else 500


def _model_test_all_reason(entry: dict[str, Any]) -> str:
    if entry.get("rateLimited") is True:
        return "rate_limited"
    if entry.get("isTimeout") is True:
        return "timeout"
    if entry.get("error"):
        return str(entry["error"])[:160]
    status_code = entry.get("statusCode")
    if isinstance(status_code, int):
        return handle_probe_error(status_code)[1]
    return "model_test_failed"


def _record_probe_outcome(context: PipelineContext, *, row: dict[str, Any], outcome: _ProbeOutcome) -> int:
    capabilities = dict(row["capabilities"] or {})
    started_at = utcnow()
    finished_at = utcnow()
    details = {
        "suites": list(probe_suites(capabilities)),
        "reserved_capacity": True,
        **outcome.details,
    }
    request_hash = hash_parts(str(row["id"]), started_at.date().isoformat(), PROBE_SUITE_VERSION, "basic")
    with context.repository.database.transaction() as transaction:
        probe = context.repository.probes.record(
            transaction,
            endpoint_id=row["id"],
            suite_version=PROBE_SUITE_VERSION,
            probe_type="basic",
            request_hash=request_hash,
            passed=outcome.passed,
            http_status=outcome.http_status,
            started_at=started_at,
            finished_at=finished_at,
            details=details,
        )
        transaction.execute(
            "UPDATE provider_endpoints SET probe_status = %(status)s WHERE id = %(endpoint_id)s",
            {"status": "passed" if probe["passed"] else "failed", "endpoint_id": row["id"]},
        )
    return 1


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
