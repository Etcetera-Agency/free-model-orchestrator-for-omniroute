from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from fmo.idempotency import hash_parts, utcnow
from fmo.omniroute import OmniRouteRequestError
from fmo.persistence import Repository
from fmo.probes import handle_probe_error, probe_suites

SWEEP_SUITE_VERSION = "provider-sweep-v2-model-test"


@dataclass(frozen=True)
class ProviderSweepItem:
    endpoint_id: str
    provider_model_id: str
    status: str
    http_status: int | None
    reason: str | None = None


@dataclass(frozen=True)
class ProviderSweepResult:
    provider: str
    dry_run: bool
    scanned: int
    probed: int
    passed: int
    failed: int
    skipped: int
    items: list[ProviderSweepItem] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return self.probed > 0 and not self.dry_run


def sweep_provider_models(
    repository: Repository,
    client: Any,
    *,
    provider: str,
    limit: int = 0,
    offset: int = 0,
    force: bool = False,
    dry_run: bool = False,
    delay_seconds: float = 0.0,
    timeout_seconds: float = 0.0,
    log: Callable[[str], None] | None = None,
    sleep=time.sleep,
) -> ProviderSweepResult:
    if not provider:
        raise ValueError("provider_required")
    rows = _provider_endpoint_rows(repository, provider=provider, limit=limit, offset=offset)
    items: list[ProviderSweepItem] = []
    probed = 0
    passed = 0
    failed = 0
    skipped = 0
    original_timeout = getattr(client, "timeout", None)
    if timeout_seconds > 0 and original_timeout is not None:
        client.timeout = timeout_seconds
    try:
        for row in rows:
            if not force and row["probe_status"] == "passed":
                skipped += 1
                items.append(
                    ProviderSweepItem(
                        endpoint_id=str(row["id"]),
                        provider_model_id=row["provider_model_id"],
                        status="skipped_passed",
                        http_status=None,
                        reason="already_passed",
                    )
                )
                continue
            if dry_run:
                skipped += 1
                items.append(
                    ProviderSweepItem(
                        endpoint_id=str(row["id"]),
                        provider_model_id=row["provider_model_id"],
                        status="would_probe",
                        http_status=None,
                    )
                )
                continue
            if probed and delay_seconds > 0:
                sleep(delay_seconds)
            if log is not None:
                log(f"model_test_start model={row['provider_model_id']}")
            outcome = _probe_one(repository, client, provider=provider, row=row)
            if log is not None:
                log(
                    f"model_test_done model={outcome.provider_model_id} status={outcome.status} "
                    f"http={outcome.http_status} reason={outcome.reason or '-'}"
                )
            probed += 1
            passed += int(outcome.status == "passed")
            failed += int(outcome.status == "failed")
            items.append(outcome)
    finally:
        if timeout_seconds > 0 and original_timeout is not None:
            client.timeout = original_timeout
    return ProviderSweepResult(
        provider=provider,
        dry_run=dry_run,
        scanned=len(rows),
        probed=probed,
        passed=passed,
        failed=failed,
        skipped=skipped,
        items=items,
    )


def format_provider_sweep_result(result: ProviderSweepResult, *, as_json: bool = False) -> str:
    if as_json:
        return json.dumps(
            {
                "provider": result.provider,
                "dry_run": result.dry_run,
                "scanned": result.scanned,
                "probed": result.probed,
                "passed": result.passed,
                "failed": result.failed,
                "skipped": result.skipped,
                "items": [item.__dict__ for item in result.items],
            },
            sort_keys=True,
        )
    lines = [
        (
            f"provider={result.provider} dry_run={result.dry_run} scanned={result.scanned} "
            f"probed={result.probed} passed={result.passed} failed={result.failed} skipped={result.skipped}"
        )
    ]
    for item in result.items:
        suffix = f" reason={item.reason}" if item.reason else ""
        lines.append(f"{item.status}\t{item.provider_model_id}\thttp={item.http_status}{suffix}")
    return "\n".join(lines)


def _provider_endpoint_rows(repository: Repository, *, provider: str, limit: int, offset: int) -> list[dict[str, Any]]:
    limit_sql = "" if limit <= 0 else "LIMIT %(limit)s"
    with repository.database.transaction() as transaction:
        return [
            dict(row)
            for row in transaction.execute(
                f"""
                SELECT pe.id, pe.provider_model_id, pe.capabilities, pe.probe_status,
                       p.omniroute_provider_id, pa.omniroute_connection_id
                FROM provider_endpoints pe
                JOIN providers p ON p.id = pe.provider_id
                JOIN provider_accounts pa ON pa.id = pe.provider_account_id
                WHERE p.omniroute_provider_id = %(provider)s
                  AND pe.removed_at IS NULL
                ORDER BY pe.provider_model_id
                {limit_sql}
                OFFSET %(offset)s
                """,
                {"provider": provider, "limit": limit, "offset": offset},
            ).fetchall()
        ]


def _probe_one(repository: Repository, client: Any, *, provider: str, row: dict[str, Any]) -> ProviderSweepItem:
    capabilities = dict(row["capabilities"] or {})
    started_at = utcnow()
    http_status = 200
    details = {
        "provider_sweep": True,
        "omniroute_model_test": True,
        "suites": list(probe_suites(capabilities)),
        "previous_probe_status": row["probe_status"],
        "connection_id": row["omniroute_connection_id"],
    }
    try:
        response = _run_model_test(
            client,
            provider=provider,
            model=row["provider_model_id"],
            connection_id=row["omniroute_connection_id"],
        )
        http_status = response["http_status"]
        body = response["body"]
        passed = http_status < 400 and body.get("status") == "ok"
        details.update(
            {
                "response_status": body.get("status"),
                "status_code": body.get("statusCode"),
                "rate_limited": body.get("rateLimited") is True,
                "retry_after": body.get("retryAfter"),
                "is_timeout": body.get("isTimeout") is True,
            }
        )
        if body.get("responseText"):
            details["response_text_sample"] = str(body["responseText"])[:160]
        if not passed:
            details["error_reason"] = _model_test_reason(http_status, body)
    except OmniRouteRequestError as exc:
        http_status = exc.status_code
        passed = False
        action, reason = handle_probe_error(exc.status_code)
        details.update({"error_action": action, "error_reason": reason})
    finished_at = utcnow()
    request_hash = hash_parts(str(row["id"]), finished_at.isoformat(), SWEEP_SUITE_VERSION, "basic")
    with repository.database.transaction() as transaction:
        # AICODE-NOTE: Provider sweeps intentionally probe a provider catalog;
        # the normal pipeline probe stage stays seed-bounded for live safety.
        probe = repository.probes.record(
            transaction,
            endpoint_id=row["id"],
            suite_version=SWEEP_SUITE_VERSION,
            probe_type="provider_sweep",
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
    return ProviderSweepItem(
        endpoint_id=str(row["id"]),
        provider_model_id=row["provider_model_id"],
        status="passed" if passed else "failed",
        http_status=http_status,
        reason=details.get("error_reason"),
    )


def _run_model_test(client: Any, *, provider: str, model: str, connection_id: str | None) -> dict[str, Any]:
    payload: dict[str, Any] = {"providerId": provider, "modelId": model}
    if connection_id:
        payload["connectionId"] = connection_id
    response = client.post_response(
        "/api/models/test",
        payload,
        headers={"X-OmniRoute-No-Cache": "true"},
    )
    return {"http_status": response.status_code, "body": response.body}


def _model_test_reason(http_status: int, body: dict[str, Any]) -> str:
    if body.get("isTimeout") is True:
        return "timeout"
    if body.get("rateLimited") is True or http_status == 429:
        return "rate_limited"
    error = str(body.get("error") or "").strip()
    if error:
        return error[:160]
    action, reason = handle_probe_error(http_status)
    del action
    return reason
