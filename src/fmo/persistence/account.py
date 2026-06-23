from __future__ import annotations

from typing import Any

import psycopg

from ._base import Record, _jsonb, _many, _one, _optional


class ProviderAccountRepository:
    def upsert(
        self,
        connection: psycopg.Connection[Record],
        *,
        provider_id: Any,
        omniroute_connection_id: str | None = None,
        external_account_ref: str | None = None,
        metadata: dict[str, Any] | None = None,
        enabled: bool = True,
    ) -> Record:
        existing = _optional(
            connection,
            """
            SELECT * FROM provider_accounts
            WHERE provider_id = %(provider_id)s
              AND omniroute_connection_id IS NOT DISTINCT FROM %(omniroute_connection_id)s
            ORDER BY first_seen_at
            LIMIT 1
            """,
            {"provider_id": provider_id, "omniroute_connection_id": omniroute_connection_id},
        )
        if existing:
            return _one(
                connection,
                """
                UPDATE provider_accounts
                SET external_account_ref = %(external_account_ref)s,
                    metadata = %(metadata)s,
                    enabled = %(enabled)s,
                    last_seen_at = now()
                WHERE id = %(id)s
                RETURNING *
                """,
                {
                    "id": existing["id"],
                    "external_account_ref": external_account_ref,
                    "metadata": _jsonb(metadata or {}),
                    "enabled": enabled,
                },
            )
        return _one(
            connection,
            """
            INSERT INTO provider_accounts (
              provider_id, omniroute_connection_id, external_account_ref,
              metadata, enabled
            )
            VALUES (
              %(provider_id)s, %(omniroute_connection_id)s,
              %(external_account_ref)s, %(metadata)s, %(enabled)s
            )
            RETURNING *
            """,
            {
                "provider_id": provider_id,
                "omniroute_connection_id": omniroute_connection_id,
                "external_account_ref": external_account_ref,
                "metadata": _jsonb(metadata or {}),
                "enabled": enabled,
            },
        )

    def list_for_provider(
        self,
        connection: psycopg.Connection[Record],
        *,
        omniroute_instance_id: str,
        omniroute_provider_id: str,
    ) -> list[Record]:
        return _many(
            connection,
            """
            SELECT pa.*
            FROM provider_accounts pa
            JOIN providers p ON p.id = pa.provider_id
            WHERE p.omniroute_instance_id = %(omniroute_instance_id)s
              AND p.omniroute_provider_id = %(omniroute_provider_id)s
            ORDER BY pa.first_seen_at, pa.id
            """,
            {
                "omniroute_instance_id": omniroute_instance_id,
                "omniroute_provider_id": omniroute_provider_id,
            },
        )
