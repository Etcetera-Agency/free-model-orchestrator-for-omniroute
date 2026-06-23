from __future__ import annotations

from typing import Any

import psycopg

from ._base import Record, _jsonb, _one


class CanonicalModelRepository:
    def upsert(
        self,
        connection: psycopg.Connection[Record],
        *,
        canonical_slug: str,
        lab: str | None = None,
        family: str | None = None,
        version: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Record:
        return _one(
            connection,
            """
            INSERT INTO canonical_models (canonical_slug, lab, family, version, metadata)
            VALUES (%(canonical_slug)s, %(lab)s, %(family)s, %(version)s, %(metadata)s)
            ON CONFLICT (canonical_slug)
            DO UPDATE SET
              lab = EXCLUDED.lab,
              family = EXCLUDED.family,
              version = EXCLUDED.version,
              metadata = EXCLUDED.metadata,
              updated_at = now()
            RETURNING *
            """,
            {
                "canonical_slug": canonical_slug,
                "lab": lab,
                "family": family,
                "version": version,
                "metadata": _jsonb(metadata or {}),
            },
        )
