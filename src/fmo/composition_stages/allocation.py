from __future__ import annotations

from fmo.allocation import allocate_globally, build_priority_combo, validate_plan
from fmo.config import DEFAULT_AUTO_ROUTER_TAIL, configured_router_entry, is_configured_router
from fmo.forecast import apply_historical_reserve, cold_start_demand, protected_demand
from fmo.idempotency import hash_parts
from fmo.pipeline import PipelineContext, StageResult
from fmo.quota_normalize import remaining_amount

from ._base import StageDependencies
from ._helpers import _effect_result
from .roles import _latest_remaining_by_pool, _roles_needing_quality_recalibration


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


def _allocation_stage(_dependencies: StageDependencies, context: PipelineContext) -> StageResult:
    with context.repository.database.transaction() as transaction:
        roles = transaction.execute("SELECT id, requirements FROM roles ORDER BY id").fetchall()
        score_rows = transaction.execute(
            """
            SELECT DISTINCT ON (rs.role_id, rs.endpoint_id)
                   rs.role_id, rs.endpoint_id, rs.total_score,
                   COALESCE(pa.quota_pool_id, pe.provider_account_id) AS quota_pool_id,
                   eas.effective_remaining, pe.provider_model_id, pe.capabilities,
                   pe.effective_context_window, pe.access_status, pe.probe_status,
                   p.omniroute_provider_id, pa.id AS provider_account_id,
                   pa.omniroute_connection_id, cm.id AS canonical_model_id,
                   cm.canonical_slug, cm.family AS canonical_family
            FROM role_scores rs
            JOIN provider_endpoints pe ON pe.id = rs.endpoint_id
            JOIN provider_accounts pa ON pa.id = pe.provider_account_id
            JOIN providers p ON p.id = pa.provider_id
            LEFT JOIN canonical_models cm ON cm.id = pe.canonical_model_id
            JOIN endpoint_access_states eas ON eas.endpoint_id = pe.id
            WHERE rs.eligibility = true
            ORDER BY rs.role_id, rs.endpoint_id, rs.calculated_at DESC
            """
        ).fetchall()
        forecast_demand = {
            row["role_id"]: float(row["protected_requests"])
            for row in transaction.execute(
                """
                SELECT DISTINCT ON (role_id) role_id, protected_requests
                FROM role_demand_forecasts
                ORDER BY role_id, created_at DESC
                """
            ).fetchall()
        }
        recalibration_roles = _roles_needing_quality_recalibration(transaction)
        pool_remaining = _latest_remaining_by_pool(transaction)
        demand = {
            role["id"]: forecast_demand.get(
                role["id"], cold_start_demand(schedule=None, bootstrap=None, role_minimum=1, global_minimum=1).value
            )
            for role in roles
        }
        endpoints = [
            {
                "id": str(row["endpoint_id"]),
                "pool": str(row["quota_pool_id"]),
                "score": float(row["total_score"]),
                "capacity": pool_remaining.get(str(row["quota_pool_id"]), remaining_amount(row["effective_remaining"])),
                "is_router": is_configured_router(str(row["provider_model_id"])),
                "input": _configured_router_input(str(row["provider_model_id"])),
                "effective_context_window": int(row["effective_context_window"] or 0),
                "access": "free_quota_available" if row["access_status"] == "confirmed" else "unknown_excluded",
                "basic_probe": row["probe_status"] == "passed",
                "quota": pool_remaining.get(str(row["quota_pool_id"]), remaining_amount(row["effective_remaining"])),
                "breaker": "closed",
                "provider_model_id": str(row["provider_model_id"]),
                "provider_id": str(row["omniroute_provider_id"]),
                "connection_id": str(row["omniroute_connection_id"]) if row["omniroute_connection_id"] else None,
                "provider_account_id": str(row["provider_account_id"]),
                "quota_pool_id": str(row["quota_pool_id"]),
                "canonical_model_id": str(row["canonical_model_id"]) if row["canonical_model_id"] else None,
                "canonical_slug": str(row["canonical_slug"]) if row["canonical_slug"] else None,
                "canonical_family": str(row["canonical_family"]) if row["canonical_family"] else None,
            }
            for row in score_rows
        ]
        endpoint_by_id = {endpoint["id"]: endpoint for endpoint in endpoints}
        plan = allocate_globally([role["id"] for role in roles], endpoints, demand)
        written = 0
        for role in roles:
            if role["id"] in recalibration_roles:
                continue
            allocation = plan.allocations.get(role["id"])
            role_scores = endpoints if allocation is not None else []
            pool_usage = dict(plan.pool_usage)
            targets = []
            if allocation is not None:
                requirements = role["requirements"] or {}
                combo = build_priority_combo(
                    role["id"],
                    role_scores,
                    per_pool_cap=2,
                    demand=demand[role["id"]],
                    pool_usage=pool_usage,
                    reserved_endpoint_id=allocation.endpoint_id,
                    auto_router_tail=tuple(entry.id for entry in DEFAULT_AUTO_ROUTER_TAIL),
                    required_capabilities=set(requirements.get("capabilities", [])),
                    minimum_context=int(requirements.get("minimum_context_window") or 0),
                )
                targets = [
                    _allocation_target(endpoint_by_id[endpoint_id], priority=index + 1)
                    for index, endpoint_id in enumerate(combo.endpoints)
                ]
                combo_diagnostics = combo.diagnostics
            else:
                combo_diagnostics = {}
            pool_reports = {
                pool: {
                    "usage": usage,
                    "capacity": max(
                        (endpoint["capacity"] for endpoint in endpoints if endpoint["pool"] == pool), default=0
                    ),
                }
                for pool, usage in pool_usage.items()
            }
            validation = validate_plan(
                pool_reports or {"empty": {"usage": 0, "capacity": 0}}, role_has_primary=allocation is not None
            )
            context.repository.allocation_plans.upsert(
                transaction,
                role_id=role["id"],
                status="planned" if validation.apply else "degraded",
                targets=targets,
                constraint_report={
                    "apply": validation.apply,
                    "reason": validation.reason,
                    "role_status": validation.role_status,
                    "pool_reports": pool_reports,
                    "diversity": combo_diagnostics,
                },
                input_state_hash=hash_parts(role["id"], str(targets), str(pool_reports)),
            )
            written += 1
    return _effect_result("allocation", changed=written > 0)


def _configured_router_input(model_id: str) -> tuple[str, ...]:
    entry = configured_router_entry(model_id)
    return entry.input if entry is not None else ()


def _allocation_target(endpoint: dict, *, priority: int) -> dict:
    # AICODE-NOTE: Structured member identity is the handoff from allocation to
    # diff/apply; endpoint_id remains audit key, combo_step is OmniRoute payload.
    combo_step = {
        "kind": "model",
        "model": endpoint["provider_model_id"],
        "providerId": endpoint["provider_id"],
        "weight": 0,
    }
    if endpoint.get("connection_id"):
        combo_step["connectionId"] = endpoint["connection_id"]
    return {
        "endpoint_id": endpoint["id"],
        "priority": priority,
        "combo_step": combo_step,
        "groups": {
            "provider_id": endpoint["provider_id"],
            "provider_account_id": endpoint["provider_account_id"],
            "quota_pool_id": endpoint["quota_pool_id"],
            "canonical_model_id": endpoint.get("canonical_model_id"),
            "canonical_slug": endpoint.get("canonical_slug"),
            "canonical_family": endpoint.get("canonical_family"),
        },
        "score": endpoint["score"],
    }


def _capacity_weight(status: str) -> float:
    if status == "confirmed":
        return 1.0
    if status == "inferred":
        return 0.5
    return 0.0
