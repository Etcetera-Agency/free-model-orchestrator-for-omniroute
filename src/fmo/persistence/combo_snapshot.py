from __future__ import annotations

from typing import Any

import psycopg

from ._base import Record, _jsonb, _one, _optional


class ComboSnapshotRepository:
    def upsert(
        self,
        connection: psycopg.Connection[Record],
        *,
        role_id: str,
        state_hash: str,
        state_json: dict[str, Any],
        phase: str,
        omniroute_combo_id: str | None = None,
        run_id: Any | None = None,
    ) -> Record:
        existing = _optional(
            connection,
            """
            SELECT * FROM combo_snapshots
            WHERE role_id = %(role_id)s AND state_hash = %(state_hash)s AND phase = %(phase)s
            ORDER BY created_at
            LIMIT 1
            """,
            {"role_id": role_id, "state_hash": state_hash, "phase": phase},
        )
        if existing:
            return _one(
                connection,
                """
                UPDATE combo_snapshots
                SET created_at = now(),
                    omniroute_combo_id = COALESCE(%(omniroute_combo_id)s, omniroute_combo_id),
                    run_id = COALESCE(%(run_id)s, run_id)
                WHERE id = %(id)s
                RETURNING *
                """,
                {"id": existing["id"], "omniroute_combo_id": omniroute_combo_id, "run_id": run_id},
            )
        return _one(
            connection,
            """
            INSERT INTO combo_snapshots (
              role_id, omniroute_combo_id, state_hash, state_json, phase, run_id
            )
            VALUES (
              %(role_id)s, %(omniroute_combo_id)s, %(state_hash)s,
              %(state_json)s, %(phase)s, %(run_id)s
            )
            RETURNING *
            """,
            {
                "role_id": role_id,
                "omniroute_combo_id": omniroute_combo_id,
                "state_hash": state_hash,
                "state_json": _jsonb(state_json),
                "phase": phase,
                "run_id": run_id,
            },
        )

    def get(self, connection: psycopg.Connection[Record], snapshot_id: Any) -> Record | None:
        return _optional(connection, "SELECT * FROM combo_snapshots WHERE id = %(id)s", {"id": snapshot_id})
