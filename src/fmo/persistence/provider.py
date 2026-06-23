from __future__ import annotations

import psycopg

from ._base import Record, _one


class ProviderRepository:
    def upsert(
        self,
        connection: psycopg.Connection[Record],
        *,
        omniroute_instance_id: str,
        omniroute_provider_id: str,
        provider_type: str,
        display_name: str | None = None,
        enabled: bool = True,
        provider_group: str | None = None,
        raw_config_hash: str | None = None,
    ) -> Record:
        return _one(
            connection,
            """
            INSERT INTO providers (
              omniroute_instance_id, omniroute_provider_id, provider_type,
              display_name, enabled, provider_group, raw_config_hash
            )
            VALUES (
              %(omniroute_instance_id)s, %(omniroute_provider_id)s,
              %(provider_type)s, %(display_name)s, %(enabled)s,
              %(provider_group)s, %(raw_config_hash)s
            )
            ON CONFLICT (omniroute_instance_id, omniroute_provider_id)
            DO UPDATE SET
              provider_type = EXCLUDED.provider_type,
              display_name = EXCLUDED.display_name,
              enabled = EXCLUDED.enabled,
              provider_group = EXCLUDED.provider_group,
              raw_config_hash = EXCLUDED.raw_config_hash,
              last_seen_at = now()
            RETURNING *
            """,
            {
                "omniroute_instance_id": omniroute_instance_id,
                "omniroute_provider_id": omniroute_provider_id,
                "provider_type": provider_type,
                "display_name": display_name,
                "enabled": enabled,
                "provider_group": provider_group,
                "raw_config_hash": raw_config_hash,
            },
        )
