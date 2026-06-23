from __future__ import annotations

from decimal import Decimal
from typing import Any

import psycopg

from ._base import Record, _canonical_json, _content_hash, _free_type, _jsonb, _one, _split_model_id


class ExternalMetadataRepository:
    def store_sync_result(
        self,
        connection: psycopg.Connection[Record],
        *,
        candidates: dict[Any, Any],
        aa_snapshot: Any,
        run_id: Any | None = None,
    ) -> Record:
        raw_json = {
            "models_dev": {
                "candidates": [
                    {
                        "provider_id": candidate.provider_id,
                        "model_id": candidate.model_id,
                        "display_name": candidate.display_name,
                        "reasons": list(candidate.reasons),
                    }
                    for candidate in candidates.values()
                ]
            },
            "artificial_analysis": {
                "index_version": aa_snapshot.index_version,
                "models": [
                    {
                        "model_id": model.model_id,
                        "metrics": model.metrics,
                        "available": model.available,
                    }
                    for model in aa_snapshot.models
                ],
            },
        }
        snapshot = _one(
            connection,
            """
            INSERT INTO free_provider_registry_snapshots (
              run_id, summary_hash, raw_json
            )
            VALUES (
              %(run_id)s, %(summary_hash)s, %(raw_json)s
            )
            RETURNING *
            """,
            {
                "run_id": run_id,
                "summary_hash": _content_hash(_canonical_json(raw_json)),
                "raw_json": _jsonb(raw_json),
            },
        )
        for candidate in candidates.values():
            self._upsert_candidate(connection, candidate, snapshot_id=snapshot["id"])
        for model in aa_snapshot.models:
            self._record_aa_metrics(connection, model)
        return snapshot

    def _upsert_candidate(self, connection: psycopg.Connection[Record], candidate: Any, *, snapshot_id: Any) -> None:
        connection.execute(
            """
            INSERT INTO free_model_definitions (
              provider_id, provider_model_id, display_name, free_type,
              monthly_tokens, credit_tokens, omniroute_pool_key, source_snapshot_id
            )
            VALUES (
              %(provider_id)s, %(provider_model_id)s, %(display_name)s, %(free_type)s,
              0, 0, %(omniroute_pool_key)s, %(source_snapshot_id)s
            )
            ON CONFLICT (provider_id, provider_model_id)
            DO UPDATE SET
              display_name = EXCLUDED.display_name,
              free_type = EXCLUDED.free_type,
              omniroute_pool_key = EXCLUDED.omniroute_pool_key,
              source_snapshot_id = EXCLUDED.source_snapshot_id,
              last_seen_at = now()
            """,
            {
                "provider_id": candidate.provider_id,
                "provider_model_id": candidate.model_id,
                "display_name": candidate.display_name,
                "free_type": _free_type(candidate.reasons),
                "omniroute_pool_key": f"{candidate.provider_id}:{candidate.model_id}",
                "source_snapshot_id": snapshot_id,
            },
        )

    def _record_aa_metrics(self, connection: psycopg.Connection[Record], model: Any) -> None:
        provider_id, provider_model_id = _split_model_id(model.model_id)
        for category, value in model.metrics.items():
            connection.execute(
                """
                INSERT INTO free_provider_quality_observations (
                  provider_id, provider_model_id, category, normalized_score, confidence
                )
                VALUES (
                  %(provider_id)s, %(provider_model_id)s, %(category)s,
                  %(normalized_score)s, %(confidence)s
                )
                """,
                {
                    "provider_id": provider_id,
                    "provider_model_id": provider_model_id,
                    "category": category,
                    "normalized_score": Decimal(str(value)),
                    "confidence": "available" if model.available is not False else "unavailable",
                },
            )
