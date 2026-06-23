from __future__ import annotations

from typing import Any

import psycopg

from ._base import Record, _jsonb, _one


class RoleRepository:
    def upsert(
        self,
        connection: psycopg.Connection[Record],
        *,
        role_id: str,
        requirements: dict[str, Any],
        expected_load: dict[str, Any],
        criticality: int,
        minimum_quality_metric: str | None = None,
        minimum_quality_value: float | None = None,
        maximum_quality_metric: str | None = None,
        maximum_quality_value: float | None = None,
        quality_gate_index_version: str | None = None,
    ) -> Record:
        return _one(
            connection,
            """
            INSERT INTO roles (
              id, requirements, expected_load, criticality,
              minimum_quality_metric, minimum_quality_value,
              maximum_quality_metric, maximum_quality_value,
              quality_gate_index_version
            )
            VALUES (
              %(role_id)s, %(requirements)s, %(expected_load)s, %(criticality)s,
              %(minimum_quality_metric)s, %(minimum_quality_value)s,
              %(maximum_quality_metric)s, %(maximum_quality_value)s,
              %(quality_gate_index_version)s
            )
            ON CONFLICT (id)
            DO UPDATE SET
              requirements = EXCLUDED.requirements,
              expected_load = EXCLUDED.expected_load,
              criticality = EXCLUDED.criticality,
              minimum_quality_metric = COALESCE(EXCLUDED.minimum_quality_metric, roles.minimum_quality_metric),
              minimum_quality_value = COALESCE(EXCLUDED.minimum_quality_value, roles.minimum_quality_value),
              maximum_quality_metric = COALESCE(EXCLUDED.maximum_quality_metric, roles.maximum_quality_metric),
              maximum_quality_value = COALESCE(EXCLUDED.maximum_quality_value, roles.maximum_quality_value),
              quality_gate_index_version = COALESCE(EXCLUDED.quality_gate_index_version, roles.quality_gate_index_version)
            RETURNING *
            """,
            {
                "role_id": role_id,
                "requirements": _jsonb(requirements),
                "expected_load": _jsonb(expected_load),
                "criticality": criticality,
                "minimum_quality_metric": minimum_quality_metric,
                "minimum_quality_value": minimum_quality_value,
                "maximum_quality_metric": maximum_quality_metric,
                "maximum_quality_value": maximum_quality_value,
                "quality_gate_index_version": quality_gate_index_version,
            },
        )
