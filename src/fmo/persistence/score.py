from __future__ import annotations

from decimal import Decimal
from typing import Any

import psycopg

from ._base import Record, _jsonb, _one, _optional


class ScoreRepository:
    def upsert(
        self,
        connection: psycopg.Connection[Record],
        *,
        role_id: str,
        endpoint_id: Any,
        score_version: str,
        total_score: float,
        component_scores: dict[str, Any],
        eligibility: bool,
        input_state_hash: str,
        rejection_reasons: list[str] | None = None,
    ) -> Record:
        existing = _optional(
            connection,
            """
            SELECT * FROM role_scores
            WHERE role_id = %(role_id)s
              AND endpoint_id = %(endpoint_id)s
              AND score_version = %(score_version)s
              AND input_state_hash = %(input_state_hash)s
            ORDER BY calculated_at
            LIMIT 1
            """,
            {
                "role_id": role_id,
                "endpoint_id": endpoint_id,
                "score_version": score_version,
                "input_state_hash": input_state_hash,
            },
        )
        if existing:
            return existing
        return _one(
            connection,
            """
            INSERT INTO role_scores (
              role_id, endpoint_id, score_version, total_score, component_scores,
              eligibility, rejection_reasons, input_state_hash
            )
            VALUES (
              %(role_id)s, %(endpoint_id)s, %(score_version)s, %(total_score)s,
              %(component_scores)s, %(eligibility)s, %(rejection_reasons)s,
              %(input_state_hash)s
            )
            RETURNING *
            """,
            {
                "role_id": role_id,
                "endpoint_id": endpoint_id,
                "score_version": score_version,
                "total_score": Decimal(str(total_score)),
                "component_scores": _jsonb(component_scores),
                "eligibility": eligibility,
                "rejection_reasons": _jsonb(rejection_reasons),
                "input_state_hash": input_state_hash,
            },
        )

    def get(self, connection: psycopg.Connection[Record], score_id: Any) -> Record | None:
        return _optional(connection, "SELECT * FROM role_scores WHERE id = %(id)s", {"id": score_id})
