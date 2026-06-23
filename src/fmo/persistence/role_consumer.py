from __future__ import annotations

from typing import Any

import psycopg

from ._base import Record, _one, _trigger_type


class RoleConsumerRepository:
    def start_inventory_run(
        self,
        connection: psycopg.Connection[Record],
        *,
        source_mode: str,
        trigger_type: str,
        source_hash: str,
    ) -> Record:
        return _one(
            connection,
            """
            INSERT INTO hermes_inventory_runs (source_mode, trigger_type, source_hash, status)
            VALUES (%(source_mode)s, %(trigger_type)s, %(source_hash)s, 'running')
            RETURNING *
            """,
            {"source_mode": source_mode, "trigger_type": trigger_type, "source_hash": source_hash},
        )

    def complete_inventory_run(
        self,
        connection: psycopg.Connection[Record],
        *,
        run_id: Any,
        roles_found: int,
        consumers_found: int,
    ) -> None:
        connection.execute(
            """
            UPDATE hermes_inventory_runs
            SET status = 'completed',
                roles_found = %(roles_found)s,
                routines_found = %(consumers_found)s,
                completed_at = now()
            WHERE id = %(run_id)s
            """,
            {"run_id": run_id, "roles_found": roles_found, "consumers_found": consumers_found},
        )

    def upsert(
        self,
        connection: psycopg.Connection[Record],
        *,
        role_id: str,
        consumer_type: str,
        consumer_key: str,
        cadence: str,
        calls_per_run: float,
        source_hash: str,
    ) -> Record:
        return _one(
            connection,
            """
            INSERT INTO role_consumers (
              role_id, consumer_type, consumer_key, trigger_type,
              schedule_expression, calls_per_run, source_hash
            )
            VALUES (
              %(role_id)s, %(consumer_type)s, %(consumer_key)s, %(trigger_type)s,
              %(schedule_expression)s, %(calls_per_run)s, %(source_hash)s
            )
            ON CONFLICT (role_id, consumer_type, consumer_key)
            DO UPDATE SET
              trigger_type = EXCLUDED.trigger_type,
              schedule_expression = EXCLUDED.schedule_expression,
              calls_per_run = EXCLUDED.calls_per_run,
              source_hash = EXCLUDED.source_hash,
              last_seen_at = now(),
              active = true
            RETURNING *
            """,
            {
                "role_id": role_id,
                "consumer_type": consumer_type,
                "consumer_key": consumer_key,
                "trigger_type": _trigger_type(cadence),
                "schedule_expression": cadence,
                "calls_per_run": calls_per_run,
                "source_hash": source_hash,
            },
        )
