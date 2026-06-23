from __future__ import annotations

from typing import Any

import psycopg

from ._base import Record, _jsonb, _one, _optional


class AllocationPlanRepository:
    def upsert(
        self,
        connection: psycopg.Connection[Record],
        *,
        role_id: str,
        status: str,
        targets: list[dict[str, Any]],
        constraint_report: dict[str, Any],
        input_state_hash: str,
    ) -> Record:
        existing = _optional(
            connection,
            """
            SELECT * FROM allocation_plans
            WHERE role_id = %(role_id)s AND input_state_hash = %(input_state_hash)s
            ORDER BY created_at
            LIMIT 1
            """,
            {"role_id": role_id, "input_state_hash": input_state_hash},
        )
        if existing:
            return existing
        return _one(
            connection,
            """
            INSERT INTO allocation_plans (
              role_id, status, targets, constraint_report, input_state_hash
            )
            VALUES (
              %(role_id)s, %(status)s, %(targets)s, %(constraint_report)s,
              %(input_state_hash)s
            )
            RETURNING *
            """,
            {
                "role_id": role_id,
                "status": status,
                "targets": _jsonb(targets),
                "constraint_report": _jsonb(constraint_report),
                "input_state_hash": input_state_hash,
            },
        )

    def get(self, connection: psycopg.Connection[Record], plan_id: Any) -> Record | None:
        return _optional(connection, "SELECT * FROM allocation_plans WHERE id = %(id)s", {"id": plan_id})
