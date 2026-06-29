from __future__ import annotations

from fmo.forecast import apply_historical_reserve, cold_start_demand, protected_demand
from fmo.idempotency import hash_parts
from fmo.pipeline import PipelineContext, StageResult

from ._base import StageDependencies
from ._helpers import _effect_result


def _demand_forecast_stage(_dependencies: StageDependencies, context: PipelineContext) -> StageResult:
    with context.repository.database.transaction() as transaction:
        roles = transaction.execute("SELECT id, role_lifecycle_status FROM roles ORDER BY id").fetchall()
        consumer_rows = transaction.execute(
            """
            SELECT role_id, SUM(calls_per_run) AS calls
            FROM role_consumers
            WHERE active = true
            GROUP BY role_id
            """
        ).fetchall()
        consumer_demand = {row["role_id"]: float(row["calls"] or 0) for row in consumer_rows}
        written = 0
        for role in roles:
            previous = transaction.execute(
                """
                SELECT historical_reserve_multiplier
                FROM role_demand_forecasts
                WHERE role_id = %(role_id)s
                  AND historical_reserve_multiplier IS NOT NULL
                LIMIT 1
                """,
                {"role_id": role["id"]},
            ).fetchone()
            cold_start = cold_start_demand(
                schedule=consumer_demand.get(role["id"]),
                bootstrap=1.0 if role["role_lifecycle_status"] == "bootstrap_pending" else None,
                role_minimum=1.0,
                global_minimum=1.0,
            )
            reserve = apply_historical_reserve(
                cold_start.value,
                multiplier=1.2,
                already_applied=previous is not None,
            )
            protected = protected_demand(expected=reserve.reserved, p95=reserve.reserved, peak_multiplier=1.0)
            transaction.execute(
                """
                INSERT INTO role_demand_forecasts (
                  role_id, forecast_start, forecast_end, expected_requests,
                  protected_requests, confidence, input_state_hash, demand_source,
                  base_historical_requests, historical_reserve_multiplier,
                  cold_start_safety_multiplier, bootstrap_weight, history_weight,
                  representative_sample_count, representative_history_ready
                )
                VALUES (
                  %(role_id)s, now(), now() + interval '1 day', %(expected)s,
                  %(protected)s, 0.8000, %(hash)s, %(source)s,
                  %(base)s, %(multiplier)s, 1.0, %(bootstrap_weight)s,
                  %(history_weight)s, %(sample_count)s, %(history_ready)s
                )
                """,
                {
                    "role_id": role["id"],
                    "expected": reserve.reserved,
                    "protected": protected,
                    "hash": hash_parts(role["id"], str(reserve.reserved), cold_start.source),
                    "source": cold_start.source,
                    "base": reserve.base,
                    "multiplier": reserve.multiplier,
                    "bootstrap_weight": 1.0 if cold_start.source == "bootstrap" else 0.0,
                    "history_weight": 0.0 if cold_start.source == "bootstrap" else 1.0,
                    "sample_count": 1 if role["id"] in consumer_demand else 0,
                    "history_ready": role["id"] in consumer_demand,
                },
            )
            written += 1
    return _effect_result("demand-forecast", changed=written > 0)
