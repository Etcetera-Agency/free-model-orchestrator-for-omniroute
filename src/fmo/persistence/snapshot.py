from __future__ import annotations

from typing import Any

import psycopg

from ._base import Record, _canonical_json, _content_hash, _one, _optional


class SnapshotRepository:
    def store_quota_source(
        self,
        connection: psycopg.Connection[Record],
        *,
        source_url: str,
        source_type: str,
        payload: dict[str, Any],
        title: str | None = None,
        http_status: int | None = None,
    ) -> Record:
        normalized_content = _canonical_json(payload)
        content_hash = _content_hash(normalized_content)
        existing = _optional(
            connection,
            """
            SELECT * FROM quota_source_snapshots
            WHERE source_url = %(source_url)s AND content_hash = %(content_hash)s
            """,
            {"source_url": source_url, "content_hash": content_hash},
        )
        if existing:
            return existing
        return _one(
            connection,
            """
            INSERT INTO quota_source_snapshots (
              source_url, source_type, title, http_status, content_hash,
              normalized_content
            )
            VALUES (
              %(source_url)s, %(source_type)s, %(title)s, %(http_status)s,
              %(content_hash)s, %(normalized_content)s
            )
            RETURNING *
            """,
            {
                "source_url": source_url,
                "source_type": source_type,
                "title": title,
                "http_status": http_status,
                "content_hash": content_hash,
                "normalized_content": normalized_content,
            },
        )

    def count_by_hash(self, connection: psycopg.Connection[Record], content_hash: str) -> int:
        row = _one(
            connection,
            "SELECT count(*) AS total FROM quota_source_snapshots WHERE content_hash = %(content_hash)s",
            {"content_hash": content_hash},
        )
        return int(row["total"])
