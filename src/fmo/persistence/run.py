from __future__ import annotations

from typing import Any

import psycopg

from ._base import Record, _jsonb, _many, _one, _optional


class RunRepository:
    def create(
        self,
        connection: psycopg.Connection[Record],
        *,
        run_type: str,
        trigger: str,
        status: str,
        code_version: str,
        config_hash: str,
        omniroute_version: str | None = None,
        error_json: dict[str, Any] | None = None,
    ) -> Record:
        return _one(
            connection,
            """
            INSERT INTO sync_runs (
              run_type, trigger, status, code_version, config_hash,
              omniroute_version, error_json
            )
            VALUES (
              %(run_type)s, %(trigger)s, %(status)s, %(code_version)s,
              %(config_hash)s, %(omniroute_version)s, %(error_json)s
            )
            RETURNING *
            """,
            {
                "run_type": run_type,
                "trigger": trigger,
                "status": status,
                "code_version": code_version,
                "config_hash": config_hash,
                "omniroute_version": omniroute_version,
                "error_json": _jsonb(error_json),
            },
        )

    def get(self, connection: psycopg.Connection[Record], run_id: Any) -> Record | None:
        return _optional(connection, "SELECT * FROM sync_runs WHERE id = %(id)s", {"id": run_id})

    def list(self, connection: psycopg.Connection[Record]) -> list[Record]:
        return _many(connection, "SELECT * FROM sync_runs ORDER BY started_at, id")

    def finish(
        self,
        connection: psycopg.Connection[Record],
        run_id: Any,
        *,
        status: str,
        stages: list[dict[str, Any]],
    ) -> Record:
        return _one(
            connection,
            """
            UPDATE sync_runs
            SET status = %(status)s,
                finished_at = now(),
                error_json = %(error_json)s
            WHERE id = %(id)s
            RETURNING *
            """,
            {
                "id": run_id,
                "status": status,
                "error_json": _jsonb({"stages": stages}),
            },
        )

    def last_successful_stage(
        self,
        connection: psycopg.Connection[Record],
        *,
        stage_name: str,
        idempotency_key: str,
    ) -> dict[str, Any] | None:
        for run in reversed(self.list(connection)):
            payload = run.get("error_json")
            if not isinstance(payload, dict):
                continue
            for stage in payload.get("stages", []):
                if not isinstance(stage, dict):
                    continue
                if (
                    stage.get("name") == stage_name
                    and stage.get("idempotency_key") == idempotency_key
                    and stage.get("status") == "success"
                    and not stage.get("skipped")
                ):
                    return stage
        return None
