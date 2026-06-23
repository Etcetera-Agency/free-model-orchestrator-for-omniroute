from __future__ import annotations

from typing import Any

import psycopg

from ._base import Record, _jsonb, _one, _optional


class ProbeRepository:
    def record(
        self,
        connection: psycopg.Connection[Record],
        *,
        endpoint_id: Any,
        suite_version: str,
        probe_type: str,
        request_hash: str,
        passed: bool,
        started_at: Any,
        finished_at: Any,
        http_status: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> Record:
        existing = _optional(
            connection,
            """
            SELECT * FROM endpoint_probes
            WHERE endpoint_id = %(endpoint_id)s AND request_hash = %(request_hash)s
            ORDER BY started_at
            LIMIT 1
            """,
            {"endpoint_id": endpoint_id, "request_hash": request_hash},
        )
        if existing:
            return existing
        return _one(
            connection,
            """
            INSERT INTO endpoint_probes (
              endpoint_id, suite_version, probe_type, request_hash, passed,
              http_status, details, started_at, finished_at
            )
            VALUES (
              %(endpoint_id)s, %(suite_version)s, %(probe_type)s,
              %(request_hash)s, %(passed)s, %(http_status)s, %(details)s,
              %(started_at)s, %(finished_at)s
            )
            RETURNING *
            """,
            {
                "endpoint_id": endpoint_id,
                "suite_version": suite_version,
                "probe_type": probe_type,
                "request_hash": request_hash,
                "passed": passed,
                "http_status": http_status,
                "details": _jsonb(details or {}),
                "started_at": started_at,
                "finished_at": finished_at,
            },
        )

    def get(self, connection: psycopg.Connection[Record], probe_id: Any) -> Record | None:
        return _optional(connection, "SELECT * FROM endpoint_probes WHERE id = %(id)s", {"id": probe_id})

    def count_by_request_hash(self, connection: psycopg.Connection[Record], request_hash: str) -> int:
        row = _one(
            connection,
            "SELECT count(*) AS total FROM endpoint_probes WHERE request_hash = %(request_hash)s",
            {"request_hash": request_hash},
        )
        return int(row["total"])
