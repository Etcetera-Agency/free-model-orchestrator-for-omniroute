from __future__ import annotations

from datetime import timedelta
from typing import Any

from psycopg.types.json import Jsonb

from fmo.access import classify_access
from fmo.idempotency import utcnow
from fmo.pipeline import PipelineContext, StageResult
from fmo.quota_normalize import quota_metric as _quota_metric

from ._base import StageDependencies
from ._helpers import _effect_result
from .allocation import _capacity_weight


def _access_classification_stage(_dependencies: StageDependencies, context: PipelineContext) -> StageResult:
    with context.repository.database.transaction() as transaction:
        rows = transaction.execute(
            """
            SELECT DISTINCT ON (pe.id)
                   pe.id AS endpoint_id, pe.provider_account_id, pe.provider_model_id,
                   p.omniroute_provider_id, qr.id AS quota_rule_id, qr.limits,
                   qr.reset_policy, qr.hard_stop_capable, qr.confidence,
                   fmd.status AS free_definition_status
            FROM provider_endpoints pe
            JOIN provider_accounts pa ON pa.id = pe.provider_account_id
            JOIN providers p ON p.id = pa.provider_id
            LEFT JOIN free_model_definitions fmd
              ON fmd.provider_id = p.omniroute_provider_id
             AND fmd.provider_model_id = pe.provider_model_id
            LEFT JOIN quota_rules qr
              ON qr.provider_id = p.id
             AND qr.model_pattern = pe.provider_model_id
             AND qr.status = 'active'
            WHERE pe.canonical_model_id IS NOT NULL
            ORDER BY pe.id, qr.created_at DESC NULLS LAST
            """
        ).fetchall()
        lost_free_rows = [
            row for row in rows if row["quota_rule_id"] is None and row["free_definition_status"] == "inactive"
        ]
        missing_rows = [
            row for row in rows if row["quota_rule_id"] is None and row["free_definition_status"] != "inactive"
        ]
        for row in lost_free_rows:
            _record_lost_free_access_state(transaction, row["endpoint_id"])
        if missing_rows:
            return StageResult(status="partial_stale", reason="quota_rule_missing")
        written = 0
        for row in [item for item in rows if item["quota_rule_id"] is not None]:
            metric, limit = _quota_metric(row["limits"])
            reset_at = utcnow() + timedelta(days=1)
            evidence = {
                "quota_rule": True,
                "limit": limit,
                "remaining": limit,
                "reset_at": reset_at.isoformat(),
                "hard_stop": row["hard_stop_capable"],
                "confidence": float(row["confidence"]),
                "remaining_source": "assumed",
                "daily_budget_source": "research",
            }
            decision = classify_access(evidence)
            status = _canonical_access_status(decision.status)
            transaction.execute(
                """
                INSERT INTO endpoint_access_states (
                  endpoint_id, quota_rule_id, status, reason_code, effective_remaining,
                  reset_at, hard_stop_capable, evidence
                )
                VALUES (
                  %(endpoint_id)s, %(quota_rule_id)s, %(status)s, %(reason_code)s,
                  %(effective_remaining)s, %(reset_at)s, %(hard_stop_capable)s, %(evidence)s
                )
                ON CONFLICT (endpoint_id)
                DO UPDATE SET
                  quota_rule_id = EXCLUDED.quota_rule_id,
                  status = EXCLUDED.status,
                  reason_code = EXCLUDED.reason_code,
                  effective_remaining = EXCLUDED.effective_remaining,
                  reset_at = EXCLUDED.reset_at,
                  hard_stop_capable = EXCLUDED.hard_stop_capable,
                  evidence = EXCLUDED.evidence,
                  classified_at = now()
                """,
                {
                    "endpoint_id": row["endpoint_id"],
                    "quota_rule_id": row["quota_rule_id"],
                    "status": status,
                    "reason_code": decision.reason_code,
                    "effective_remaining": Jsonb({metric: limit}),
                    "reset_at": reset_at,
                    "hard_stop_capable": row["hard_stop_capable"],
                    "evidence": Jsonb({**evidence, "free_access": status == "confirmed"}),
                },
            )
            group = transaction.execute(
                """
                INSERT INTO quota_attribution_groups (
                  provider_id, scope_type, scope_key, status, source, limit_type,
                  request_limit, token_limit, reset_rule_json, confidence,
                  capacity_weight, evidence_json
                )
                VALUES (
                  %(provider_id)s, 'account', %(scope_key)s, %(status)s, 'quota-research',
                  %(limit_type)s, %(request_limit)s, %(token_limit)s, %(reset_rule_json)s,
                  %(confidence)s, %(capacity_weight)s, %(evidence_json)s
                )
                RETURNING *
                """,
                {
                    "provider_id": row["omniroute_provider_id"],
                    "scope_key": str(row["provider_account_id"]),
                    "status": status,
                    "limit_type": metric,
                    "request_limit": limit if metric == "requests" else None,
                    "token_limit": limit if metric == "tokens" else None,
                    "reset_rule_json": Jsonb(row["reset_policy"]),
                    "confidence": row["confidence"],
                    "capacity_weight": _capacity_weight(status),
                    "evidence_json": Jsonb([evidence]),
                },
            ).fetchone()
            transaction.execute(
                """
                INSERT INTO endpoint_quota_attribution (
                  endpoint_id, account_or_connection_id, quota_attribution_group_id,
                  attribution_status, evidence_json
                )
                VALUES (
                  %(endpoint_id)s, %(account_id)s, %(group_id)s,
                  %(status)s, %(evidence_json)s
                )
                """,
                {
                    "endpoint_id": row["endpoint_id"],
                    "account_id": str(row["provider_account_id"]),
                    "group_id": group["id"],
                    "status": status,
                    "evidence_json": Jsonb([evidence]),
                },
            )
            transaction.execute(
                "UPDATE provider_endpoints SET access_status = %(status)s WHERE id = %(endpoint_id)s",
                {"status": status, "endpoint_id": row["endpoint_id"]},
            )
            written += 1
    return _effect_result("access-classification", changed=written > 0)


def _record_lost_free_access_state(transaction: Any, endpoint_id: Any) -> None:
    transaction.execute(
        """
        UPDATE provider_endpoints
        SET access_status = 'rejected'
        WHERE id = %(endpoint_id)s
        """,
        {"endpoint_id": endpoint_id},
    )
    transaction.execute(
        """
        INSERT INTO endpoint_access_states (
          endpoint_id, status, reason_code, effective_remaining,
          reset_at, hard_stop_capable, evidence
        )
        VALUES (
          %(endpoint_id)s, 'rejected', 'lost_free_status',
          '{}'::jsonb, NULL, false, '{"free_access": false}'::jsonb
        )
        ON CONFLICT (endpoint_id)
        DO UPDATE SET
          status = EXCLUDED.status,
          reason_code = EXCLUDED.reason_code,
          effective_remaining = EXCLUDED.effective_remaining,
          reset_at = EXCLUDED.reset_at,
          hard_stop_capable = EXCLUDED.hard_stop_capable,
          evidence = EXCLUDED.evidence,
          classified_at = now()
        """,
        {"endpoint_id": endpoint_id},
    )


def _canonical_access_status(access_status: str) -> str:
    if access_status in {"free_unlimited", "free_quota_available"}:
        return "confirmed"
    if access_status == "free_promotional_available":
        return "inferred"
    return "unknown"


def _deactivate_lost_free_models(transaction: Any, lost_models: set[tuple[str, str]]) -> None:
    for provider_id, model_id in lost_models:
        # AICODE-NOTE: lost-free detection is the only path that turns quota
        # rules inactive; provider-model rows stay additive and are not deleted.
        transaction.execute(
            """
            UPDATE quota_rules qr
            SET status = 'inactive'
            FROM providers p
            WHERE qr.provider_id = p.id
              AND p.omniroute_provider_id = %(provider_id)s
              AND qr.model_pattern = %(model_id)s
            """,
            {"provider_id": provider_id, "model_id": model_id},
        )
        transaction.execute(
            """
            UPDATE provider_endpoints pe
            SET access_status = 'rejected'
            FROM provider_accounts pa
            JOIN providers p ON p.id = pa.provider_id
            WHERE pe.provider_account_id = pa.id
              AND p.omniroute_provider_id = %(provider_id)s
              AND pe.provider_model_id = %(model_id)s
            """,
            {"provider_id": provider_id, "model_id": model_id},
        )
        transaction.execute(
            """
            UPDATE free_model_definitions
            SET status = 'inactive'
            WHERE provider_id = %(provider_id)s
              AND provider_model_id = %(model_id)s
            """,
            {"provider_id": provider_id, "model_id": model_id},
        )
