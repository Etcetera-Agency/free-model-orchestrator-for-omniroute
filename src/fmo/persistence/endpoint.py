from __future__ import annotations

from typing import Any

import psycopg

from ._base import Record, _jsonb, _one, _optional


class ProviderEndpointRepository:
    def upsert(
        self,
        connection: psycopg.Connection[Record],
        *,
        provider_account_id: Any,
        provider_model_id: str,
        model_type: str = "chat",
        canonical_model_id: Any | None = None,
        lifecycle_status: str,
        access_status: str,
        probe_status: str = "not_run",
        capabilities: dict[str, Any] | None = None,
        metadata_hash: str | None = None,
    ) -> Record:
        return _one(
            connection,
            """
            INSERT INTO provider_endpoints (
              provider_account_id, provider_model_id, model_type,
              canonical_model_id, lifecycle_status, access_status,
              probe_status, capabilities, metadata_hash
            )
            VALUES (
              %(provider_account_id)s, %(provider_model_id)s, %(model_type)s,
              %(canonical_model_id)s, %(lifecycle_status)s, %(access_status)s,
              %(probe_status)s, %(capabilities)s, %(metadata_hash)s
            )
            ON CONFLICT (provider_account_id, provider_model_id, model_type)
            DO UPDATE SET
              canonical_model_id = EXCLUDED.canonical_model_id,
              lifecycle_status = EXCLUDED.lifecycle_status,
              access_status = EXCLUDED.access_status,
              probe_status = EXCLUDED.probe_status,
              capabilities = EXCLUDED.capabilities,
              metadata_hash = EXCLUDED.metadata_hash,
              last_seen_at = now()
            RETURNING *
            """,
            {
                "provider_account_id": provider_account_id,
                "provider_model_id": provider_model_id,
                "model_type": model_type,
                "canonical_model_id": canonical_model_id,
                "lifecycle_status": lifecycle_status,
                "access_status": access_status,
                "probe_status": probe_status,
                "capabilities": _jsonb(capabilities or {}),
                "metadata_hash": metadata_hash,
            },
        )

    def get(self, connection: psycopg.Connection[Record], endpoint_id: Any) -> Record | None:
        return _optional(connection, "SELECT * FROM provider_endpoints WHERE id = %(id)s", {"id": endpoint_id})
