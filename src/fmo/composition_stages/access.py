from __future__ import annotations

from typing import Any

from psycopg.types.json import Jsonb

from fmo.pipeline import PipelineContext, StageResult

from ._base import StageDependencies
from ._helpers import _effect_result

OMNIROUTE_DELEGATED_REMAINING = 1_000_000_000


def _access_classification_stage(_dependencies: StageDependencies, context: PipelineContext) -> StageResult:
    with context.repository.database.transaction() as transaction:
        rows = transaction.execute(
            """
            SELECT pe.id AS endpoint_id,
                   fmd.status AS free_definition_status
            FROM provider_endpoints pe
            JOIN provider_accounts pa ON pa.id = pe.provider_account_id
            JOIN providers p ON p.id = pa.provider_id
            LEFT JOIN free_model_definitions fmd
              ON fmd.provider_id = p.omniroute_provider_id
             AND fmd.provider_model_id = pe.provider_model_id
            WHERE pe.canonical_model_id IS NOT NULL
              AND pe.removed_at IS NULL
              AND p.enabled = true
              AND pa.enabled = true
            ORDER BY pe.id
            """
        ).fetchall()
        lost_free_rows = [row for row in rows if row["free_definition_status"] == "inactive"]
        for row in lost_free_rows:
            _record_lost_free_access_state(transaction, row["endpoint_id"])
        written = 0
        for row in [item for item in rows if item["free_definition_status"] != "inactive"]:
            evidence = {
                "free_access": True,
                "quota_delegated_to": "omniroute",
                "remaining_source": "omniroute",
            }
            transaction.execute(
                """
                INSERT INTO endpoint_access_states (
                  endpoint_id, status, reason_code, effective_remaining,
                  reset_at, hard_stop_capable, evidence
                )
                VALUES (
                  %(endpoint_id)s, 'confirmed', 'omniroute_free_access',
                  %(effective_remaining)s, %(reset_at)s, %(hard_stop_capable)s, %(evidence)s
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
                {
                    "endpoint_id": row["endpoint_id"],
                    "effective_remaining": Jsonb({"requests": OMNIROUTE_DELEGATED_REMAINING}),
                    "reset_at": None,
                    "hard_stop_capable": False,
                    "evidence": Jsonb(evidence),
                },
            )
            transaction.execute(
                "UPDATE provider_endpoints SET access_status = %(status)s WHERE id = %(endpoint_id)s",
                {"status": "confirmed", "endpoint_id": row["endpoint_id"]},
            )
            written += 1
    return _effect_result("access-classification", changed=bool(written or lost_free_rows))


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


def _deactivate_lost_free_models(transaction: Any, lost_models: set[tuple[str, str]]) -> None:
    for provider_id, model_id in lost_models:
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
