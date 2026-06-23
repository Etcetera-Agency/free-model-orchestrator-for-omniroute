from __future__ import annotations

from typing import Any

import psycopg

from ._base import Record, _canonical_json, _content_hash, _jsonb, _one


class FreeRegistryRepository:
    def store_outcome(
        self,
        connection: psycopg.Connection[Record],
        *,
        outcome: Any,
        run_id: Any | None = None,
    ) -> Record:
        free_models_hash = _content_hash(_canonical_json(outcome.free_models_payload))
        rankings_hash = _content_hash(_canonical_json(outcome.rankings_payload))
        raw_json = {
            "free_models": outcome.free_models_payload,
            "rankings": outcome.rankings_payload,
            "sync_outcome": {
                "model_count": outcome.model_count,
                "drift": [list(item) for item in outcome.drift],
                "errors": outcome.errors,
            },
        }
        snapshot = _one(
            connection,
            """
            INSERT INTO free_provider_registry_snapshots (
              run_id, free_models_hash, rankings_hashes, raw_json
            )
            VALUES (
              %(run_id)s, %(free_models_hash)s, %(rankings_hashes)s, %(raw_json)s
            )
            RETURNING *
            """,
            {
                "run_id": run_id,
                "free_models_hash": free_models_hash,
                "rankings_hashes": _jsonb({"free_provider_rankings": rankings_hash}),
                "raw_json": _jsonb(raw_json),
            },
        )
        for item in outcome.free_models_payload.get("models", []):
            self.upsert_model_definition(connection, item, snapshot_id=snapshot["id"])
        return snapshot

    def upsert_model_definition(
        self,
        connection: psycopg.Connection[Record],
        item: dict[str, Any],
        *,
        snapshot_id: Any,
    ) -> Record | None:
        if item.get("authType") == "web_cookie":
            return None
        return _one(
            connection,
            """
            INSERT INTO free_model_definitions (
              provider_id, provider_model_id, display_name, free_type,
              monthly_tokens, credit_tokens, omniroute_pool_key, tos_verdict,
              source_snapshot_id
            )
            VALUES (
              %(provider_id)s, %(provider_model_id)s, %(display_name)s,
              %(free_type)s, %(monthly_tokens)s, %(credit_tokens)s,
              %(omniroute_pool_key)s, %(tos_verdict)s, %(source_snapshot_id)s
            )
            ON CONFLICT (provider_id, provider_model_id)
            DO UPDATE SET
              display_name = EXCLUDED.display_name,
              free_type = EXCLUDED.free_type,
              monthly_tokens = EXCLUDED.monthly_tokens,
              credit_tokens = EXCLUDED.credit_tokens,
              omniroute_pool_key = EXCLUDED.omniroute_pool_key,
              tos_verdict = EXCLUDED.tos_verdict,
              source_snapshot_id = EXCLUDED.source_snapshot_id,
              last_seen_at = now()
            RETURNING *
            """,
            {
                "provider_id": item["provider"],
                "provider_model_id": item["modelId"],
                "display_name": item.get("displayName"),
                "free_type": item["freeType"],
                "monthly_tokens": item.get("monthlyTokens") or 0,
                "credit_tokens": item.get("creditTokens") or 0,
                "omniroute_pool_key": item.get("poolKey"),
                "tos_verdict": item.get("tos"),
                "source_snapshot_id": snapshot_id,
            },
        )
