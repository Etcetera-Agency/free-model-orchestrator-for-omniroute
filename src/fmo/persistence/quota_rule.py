from __future__ import annotations

from decimal import Decimal
from typing import Any

import psycopg

from ._base import Record, _jsonb, _one, _optional


class QuotaRuleRepository:
    def upsert(
        self,
        connection: psycopg.Connection[Record],
        *,
        provider_id: Any,
        provider_account_id: Any | None,
        source_snapshot_id: Any | None,
        model_pattern: str,
        access_type: str,
        limits: dict[str, Any],
        reset_policy: dict[str, Any],
        hard_stop_capable: bool,
        confidence: float,
        status: str,
        rule_hash: str,
    ) -> Record:
        existing = _optional(
            connection, "SELECT * FROM quota_rules WHERE rule_hash = %(rule_hash)s", {"rule_hash": rule_hash}
        )
        if existing:
            return existing
        return _one(
            connection,
            """
            INSERT INTO quota_rules (
              provider_id, provider_account_id, source_snapshot_id, model_pattern,
              access_type, limits, reset_policy, hard_stop_capable, confidence,
              status, rule_hash
            )
            VALUES (
              %(provider_id)s, %(provider_account_id)s, %(source_snapshot_id)s,
              %(model_pattern)s, %(access_type)s, %(limits)s, %(reset_policy)s,
              %(hard_stop_capable)s, %(confidence)s, %(status)s, %(rule_hash)s
            )
            RETURNING *
            """,
            {
                "provider_id": provider_id,
                "provider_account_id": provider_account_id,
                "source_snapshot_id": source_snapshot_id,
                "model_pattern": model_pattern,
                "access_type": access_type,
                "limits": _jsonb(limits),
                "reset_policy": _jsonb(reset_policy),
                "hard_stop_capable": hard_stop_capable,
                "confidence": Decimal(str(confidence)),
                "status": status,
                "rule_hash": rule_hash,
            },
        )

    def get(self, connection: psycopg.Connection[Record], rule_id: Any) -> Record | None:
        return _optional(connection, "SELECT * FROM quota_rules WHERE id = %(id)s", {"id": rule_id})
