from __future__ import annotations

import psycopg

from ._base import Record, _optional


class LockRepository:
    def acquire(self, connection: psycopg.Connection[Record], name: str) -> str | None:
        row = _optional(
            connection,
            """
            INSERT INTO sync_runs (run_type, trigger, status, code_version, config_hash)
            VALUES ('lock', %(name)s, 'held', 'lock', %(name)s)
            ON CONFLICT (trigger)
            WHERE run_type = 'lock'
              AND status = 'held'
              AND finished_at IS NULL
            DO NOTHING
            RETURNING id
            """,
            {"name": name},
        )
        if row is None:
            return None
        return str(row["id"])

    def release(self, connection: psycopg.Connection[Record], token: str) -> None:
        connection.execute(
            """
            UPDATE sync_runs
            SET status = 'released',
                finished_at = now()
            WHERE id = %(id)s
              AND run_type = 'lock'
              AND status = 'held'
              AND finished_at IS NULL
            """,
            {"id": token},
        )
