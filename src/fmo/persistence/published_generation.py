from __future__ import annotations

from typing import Any

import psycopg

from ._base import Record, _jsonb, _one, _optional


class PublishedGenerationRepository:
    def upsert(
        self,
        connection: psycopg.Connection[Record],
        *,
        generation: str,
        payload_hash: str,
        payload_json: dict[str, Any],
        status: str,
    ) -> Record:
        return _one(
            connection,
            """
            INSERT INTO published_generations (
              generation, payload_hash, payload_json, status, acked_at
            )
            VALUES (
              %(generation)s, %(payload_hash)s, %(payload_json)s,
              %(status)s, now()
            )
            ON CONFLICT (generation, payload_hash)
            DO UPDATE SET
              payload_json = EXCLUDED.payload_json,
              status = EXCLUDED.status,
              acked_at = EXCLUDED.acked_at
            RETURNING *
            """,
            {
                "generation": generation,
                "payload_hash": payload_hash,
                "payload_json": _jsonb(payload_json),
                "status": status,
            },
        )

    def get(self, connection: psycopg.Connection[Record], generation: str, payload_hash: str) -> Record | None:
        return _optional(
            connection,
            """
            SELECT *
            FROM published_generations
            WHERE generation = %(generation)s
              AND payload_hash = %(payload_hash)s
            """,
            {"generation": generation, "payload_hash": payload_hash},
        )
