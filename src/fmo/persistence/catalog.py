from __future__ import annotations

from typing import Any

import psycopg

from ._base import Record, _canonical_json, _content_hash, _jsonb, _one, _optional


class ProviderCatalogRepository:
    def store_snapshot(
        self,
        connection: psycopg.Connection[Record],
        *,
        provider_id: Any,
        catalog: dict[str, Any],
        fetch_status: str,
    ) -> Record:
        catalog_hash = _content_hash(_canonical_json(catalog))
        previous = _optional(
            connection,
            """
            SELECT catalog_hash
            FROM provider_catalog_snapshots
            WHERE provider_id = %(provider_id)s AND fetch_status = 'success'
            ORDER BY fetched_at DESC
            LIMIT 1
            """,
            {"provider_id": provider_id},
        )
        snapshot = _optional(
            connection,
            """
            INSERT INTO provider_catalog_snapshots (
              provider_id, catalog_hash, raw_payload, model_count, fetch_status
            )
            VALUES (
              %(provider_id)s, %(catalog_hash)s, %(raw_payload)s,
              %(model_count)s, %(fetch_status)s
            )
            ON CONFLICT (provider_id, catalog_hash) DO NOTHING
            RETURNING *
            """,
            {
                "provider_id": provider_id,
                "catalog_hash": catalog_hash,
                "raw_payload": _jsonb(catalog),
                "model_count": len(catalog.get("models", [])),
                "fetch_status": fetch_status,
            },
        )
        if snapshot is None:
            snapshot = _one(
                connection,
                """
                SELECT *
                FROM provider_catalog_snapshots
                WHERE provider_id = %(provider_id)s AND catalog_hash = %(catalog_hash)s
                """,
                {"provider_id": provider_id, "catalog_hash": catalog_hash},
            )
        snapshot["is_unchanged"] = bool(previous and previous["catalog_hash"] == catalog_hash)
        return snapshot
