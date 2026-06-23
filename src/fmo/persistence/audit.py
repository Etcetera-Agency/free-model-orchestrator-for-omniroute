from __future__ import annotations

from typing import Any

import psycopg

from ._base import Record, _jsonb, _one, _optional


class AuditRepository:
    def record(
        self,
        connection: psycopg.Connection[Record],
        *,
        entity_type: str,
        entity_id: str,
        action: str,
        run_id: Any | None = None,
        before_json: dict[str, Any] | None = None,
        after_json: dict[str, Any] | None = None,
        reason_codes: list[str] | None = None,
        source_refs: list[dict[str, Any]] | None = None,
    ) -> Record:
        return _one(
            connection,
            """
            INSERT INTO change_log (
              run_id, entity_type, entity_id, action, before_json, after_json,
              reason_codes, source_refs
            )
            VALUES (
              %(run_id)s, %(entity_type)s, %(entity_id)s, %(action)s,
              %(before_json)s, %(after_json)s, %(reason_codes)s, %(source_refs)s
            )
            RETURNING *
            """,
            {
                "run_id": run_id,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "action": action,
                "before_json": _jsonb(before_json),
                "after_json": _jsonb(after_json),
                "reason_codes": _jsonb(reason_codes or []),
                "source_refs": _jsonb(source_refs or []),
            },
        )

    def get(self, connection: psycopg.Connection[Record], audit_id: Any) -> Record | None:
        return _optional(connection, "SELECT * FROM change_log WHERE id = %(id)s", {"id": audit_id})
