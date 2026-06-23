from __future__ import annotations

from typing import Any

from psycopg.types.json import Jsonb

from fmo.config import DEFAULT_APPLY_MIN_SAFETY_BUFFER
from fmo.idempotency import hash_parts, utcnow
from fmo.pipeline import PipelineContext, StageResult
from fmo.quota_manager import QuotaFetchError, fetch_live_quota_snapshot
from fmo.quota_research import research_quota_rule

from ._base import StageDependencies
from ._helpers import _effect_result
from .access import _deactivate_lost_free_models
from .discovery import _detect_free_model_changes


def _quota_research_stage(dependencies: StageDependencies, context: PipelineContext) -> StageResult:
    if dependencies.omniroute_client is None:
        return StageResult(status="external_dependency_failed", reason="omniroute_client_required")
    with context.repository.database.transaction() as transaction:
        changes = _detect_free_model_changes(transaction, dependencies.omniroute_client)
        if not changes.triggered:
            return _quota_research_skipped_result()
        endpoints = transaction.execute(
            """
            SELECT pe.id, pe.provider_model_id, pa.id AS account_id,
                   pa.omniroute_connection_id, p.id AS provider_id, p.omniroute_provider_id
            FROM provider_endpoints pe
            JOIN provider_accounts pa ON pa.id = pe.provider_account_id
            JOIN providers p ON p.id = pa.provider_id
            WHERE pe.canonical_model_id IS NOT NULL
            ORDER BY pe.provider_model_id
            """
        ).fetchall()
    quota_limit_hints = _quota_limit_hints(dependencies.omniroute_client)
    written = 0
    failed = 0
    first_failure_reason = "quota_rule_missing"
    today = utcnow()
    for endpoint in endpoints:
        result = research_quota_rule(
            dependencies.omniroute_client,
            provider=endpoint["omniroute_provider_id"],
            model_id=endpoint["provider_model_id"],
            today=today,
            summary_confidence_cap=0.70,
            instructor_call=dependencies.llm_runtime,
            previous_limit=quota_limit_hints.get(
                _quota_hint_key(
                    endpoint["omniroute_provider_id"],
                    endpoint["omniroute_connection_id"],
                )
            ),
        )
        if result.error is not None:
            failed += 1
            first_failure_reason = result.error.reason
            continue
        if result.snapshot is None or result.rule is None:
            failed += 1
            first_failure_reason = "quota_rule_missing"
            continue
        rule = result.rule
        claim = rule.claim
        with context.repository.database.transaction() as transaction:
            snapshot = context.repository.snapshots.store_quota_source(
                transaction,
                source_url=result.snapshot.evidence_urls[0] if result.snapshot.evidence_urls else result.snapshot.query,
                source_type="summary",
                payload={
                    "query": result.snapshot.query,
                    "answer_text": result.snapshot.answer_text,
                    "evidence_urls": list(result.snapshot.evidence_urls),
                },
            )
            context.repository.quota_rules.upsert(
                transaction,
                provider_id=endpoint["provider_id"],
                provider_account_id=endpoint["account_id"],
                source_snapshot_id=snapshot["id"],
                model_pattern=endpoint["provider_model_id"],
                access_type="free_quota",
                limits={claim.metric: claim.amount, "window": claim.window},
                reset_policy={"window": claim.window},
                hard_stop_capable=claim.hard_stop,
                confidence=rule.confidence,
                status="active",
                rule_hash=hash_parts(str(endpoint["id"]), snapshot["content_hash"], str(rule.confidence)),
            )
        written += 1
    if changes.lost:
        with context.repository.database.transaction() as transaction:
            _deactivate_lost_free_models(transaction, changes.lost)
    if failed:
        if written == 0:
            return StageResult(status="external_dependency_failed", reason=first_failure_reason)
        return StageResult(
            status="partial_stale",
            changed=written > 0,
            reason="quota_research_partial",
            details={
                "adapter": "quota-research",
                "effect": "repository_write" if written else None,
                "failed_endpoints": failed,
            },
        )
    return _effect_result("quota-research", changed=written > 0)


def _quota_research_skipped_result() -> StageResult:
    return StageResult(
        status="success",
        changed=False,
        idempotency_key="quota-research:production",
        details={
            "adapter": "quota-research",
            "effect": "idempotent_no_change",
            "reason": "no_free_model_change",
        },
    )


def _quota_limit_hints(client: Any) -> dict[str, float]:
    try:
        snapshot = fetch_live_quota_snapshot(client)
    except (QuotaFetchError, AttributeError, NotImplementedError):
        return {}
    except Exception:
        return {}
    return {
        _quota_hint_key(quota.provider, quota.connection_id): quota.limit
        for quota in snapshot.quotas.values()
        if quota.limit is not None
    }


def _quota_hint_key(provider: Any, connection_id: Any) -> str:
    return f"{provider}:{connection_id}"


def _quota_sync_stage(dependencies: StageDependencies, context: PipelineContext) -> StageResult:
    if dependencies.omniroute_client is None:
        return StageResult(status="external_dependency_failed", reason="omniroute_client_required")
    try:
        snapshot = fetch_live_quota_snapshot(dependencies.omniroute_client)
    except QuotaFetchError as exc:
        return StageResult(status="partial_stale", reason=exc.reason)
    written = 0
    with context.repository.database.transaction() as transaction:
        for quota in snapshot.quotas.values():
            account = transaction.execute(
                """
                SELECT pa.id, pa.quota_pool_id, p.omniroute_provider_id
                FROM provider_accounts pa
                JOIN providers p ON p.id = pa.provider_id
                WHERE p.omniroute_provider_id = %(provider_id)s
                  AND pa.omniroute_connection_id = %(connection_id)s
                LIMIT 1
                """,
                {"provider_id": quota.provider, "connection_id": quota.connection_id},
            ).fetchone()
            if account is None:
                continue
            quota_pool_id = account["quota_pool_id"] or _ensure_quota_pool(
                transaction,
                quota.provider,
                quota.connection_id,
                account["id"],
            )
            transaction.execute(
                """
                INSERT INTO quota_observations (
                  quota_pool_id, provider_account_id, source, metric, limit_value,
                  used_value, remaining_value, reset_at, raw_payload, observed_at
                )
                VALUES (
                  %(quota_pool_id)s, %(provider_account_id)s, 'omniroute', 'requests',
                  %(limit_value)s, %(used_value)s, %(remaining_value)s, %(reset_at)s,
                  %(raw_payload)s, %(observed_at)s
                )
                """,
                {
                    "quota_pool_id": quota_pool_id,
                    "provider_account_id": account["id"],
                    "limit_value": quota.learned_request_limit,
                    "used_value": (
                        None
                        if quota.learned_request_limit is None or quota.learned_request_remaining is None
                        else quota.learned_request_limit - quota.learned_request_remaining
                    ),
                    "remaining_value": quota.learned_request_remaining,
                    "reset_at": quota.reset_at,
                    "raw_payload": Jsonb(
                        {
                            "provider": quota.provider,
                            "connectionId": quota.connection_id,
                            "percentRemaining": quota.percent_remaining,
                            "lockedOut": quota.locked_out,
                        }
                    ),
                    "observed_at": snapshot.observed_at,
                },
            )
            transaction.execute(
                """
                UPDATE endpoint_access_states eas
                SET reset_at = %(reset_at)s,
                    evidence = COALESCE(eas.evidence, '{}'::jsonb) || %(evidence)s,
                    classified_at = now()
                FROM provider_endpoints pe
                WHERE eas.endpoint_id = pe.id
                  AND pe.provider_account_id = %(provider_account_id)s
                """,
                {
                    "reset_at": quota.reset_at,
                    # AICODE-NOTE: quota-sync refreshes live liveness only; it must
                    # not overwrite research/calibration daily budget remaining.
                    "evidence": Jsonb(
                        {
                            "remaining_source": "live_observed",
                            "percent_remaining": quota.percent_remaining,
                            "locked_out": quota.locked_out,
                            "safety_buffer": DEFAULT_APPLY_MIN_SAFETY_BUFFER,
                        }
                    ),
                    "provider_account_id": account["id"],
                },
            )
            written += 1
    return _effect_result("quota-sync", changed=written > 0)


def _ensure_quota_pool(transaction: Any, provider_id: str, connection_id: str, account_id: Any) -> Any:
    pool = transaction.execute(
        """
        INSERT INTO quota_pools (name, provider_group, reset_policy)
        VALUES (%(name)s, %(provider_group)s, %(reset_policy)s)
        ON CONFLICT (name)
        DO UPDATE SET provider_group = EXCLUDED.provider_group
        RETURNING id
        """,
        {
            "name": f"{provider_id}:{connection_id}:requests",
            "provider_group": provider_id,
            "reset_policy": Jsonb({"source": "omniroute"}),
        },
    ).fetchone()
    transaction.execute(
        "UPDATE provider_accounts SET quota_pool_id = %(quota_pool_id)s WHERE id = %(account_id)s",
        {"quota_pool_id": pool["id"], "account_id": account_id},
    )
    return pool["id"]


def _ensure_named_quota_pool(transaction: Any, provider_id: str, pool_key: str) -> Any:
    if pool_key.endswith(":requests"):
        name = pool_key
    elif pool_key.startswith(f"{provider_id}:"):
        name = f"{pool_key}:requests"
    else:
        name = f"{provider_id}:{pool_key}:requests"
    pool = transaction.execute(
        """
        INSERT INTO quota_pools (name, provider_group, reset_policy)
        VALUES (%(name)s, %(provider_group)s, %(reset_policy)s)
        ON CONFLICT (name)
        DO UPDATE SET provider_group = EXCLUDED.provider_group
        RETURNING id
        """,
        {
            "name": name,
            "provider_group": provider_id,
            "reset_policy": Jsonb({"source": "account-discovery"}),
        },
    ).fetchone()
    return pool["id"]
