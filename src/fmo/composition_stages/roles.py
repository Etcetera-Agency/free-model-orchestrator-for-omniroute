from __future__ import annotations

from datetime import datetime
from typing import Any

from fmo.context import context_eligible, effective_context_window
from fmo.forecast import quality_band_for_demand
from fmo.idempotency import hash_parts as _hash_parts
from fmo.pipeline import PipelineContext, StageResult
from fmo.quality import evaluate_quality_gate
from fmo.quota_normalize import remaining_amount as _remaining_amount
from fmo.scoring import EligibilityDecision, aa_subscore, eligible_for_scoring, latency_score_source, score_endpoint

from ._helpers import _effect_result
from ._legacy import StageDependencies, _read_current_combos

AA_SCORE_WEIGHTS = {"intelligence_index": 1.0, "coding_index": 0.5, "agentic_index": 0.5}
AA_SCORE_PERCENTILES = {
    "intelligence_index": (0.0, 100.0),
    "coding_index": (0.0, 100.0),
    "agentic_index": (0.0, 100.0),
}

_remaining_requests = _remaining_amount


def _role_lifecycle_stage(_dependencies: StageDependencies, context: PipelineContext) -> StageResult:
    with context.repository.database.transaction() as transaction:
        desired = {
            row["role_id"]
            for row in transaction.execute("SELECT DISTINCT role_id FROM role_consumers WHERE active = true").fetchall()
        }
        roles = transaction.execute("SELECT id, role_lifecycle_status FROM roles").fetchall()
        changed = 0
        for role in roles:
            if role["id"] in desired and role["role_lifecycle_status"] in {"retiring", "retired_pending_delete"}:
                transaction.execute(
                    """
                    UPDATE roles
                    SET role_lifecycle_status = 'active',
                        missing_since = NULL
                    WHERE id = %(role_id)s
                    """,
                    {"role_id": role["id"]},
                )
                changed += 1
            elif role["id"] not in desired and role["role_lifecycle_status"] in {"active", "bootstrap_pending"}:
                transaction.execute(
                    """
                    UPDATE roles
                    SET role_lifecycle_status = 'retiring',
                        missing_since = COALESCE(missing_since, now())
                    WHERE id = %(role_id)s
                    """,
                    {"role_id": role["id"]},
                )
                changed += 1
    return _effect_result("role-lifecycle", changed=changed > 0)


def _role_scoring_stage(_dependencies: StageDependencies, context: PipelineContext) -> StageResult:
    with context.repository.database.transaction() as transaction:
        if _dependencies.omniroute_client is not None:
            _seed_quality_bands(transaction, _dependencies.omniroute_client)
        roles = transaction.execute(
            """
            SELECT id, requirements, minimum_quality_metric, minimum_quality_value,
                   maximum_quality_metric, maximum_quality_value, quality_gate_index_version
            FROM roles
            ORDER BY id
            """
        ).fetchall()
        endpoints = transaction.execute(
            """
            SELECT pe.id, pe.capabilities, pe.provider_account_id, pe.access_status,
                   pe.probe_status, pe.advertised_context_window,
                   pe.provider_context_window, pe.probed_context_window,
                   pe.effective_context_window, pe.canonical_model_id,
                   eas.effective_remaining,
                   COALESCE(pa.quota_pool_id, pe.provider_account_id) AS quota_pool_id
            FROM provider_endpoints pe
            JOIN provider_accounts pa ON pa.id = pe.provider_account_id
            JOIN endpoint_access_states eas ON eas.endpoint_id = pe.id
            WHERE pe.access_status = 'confirmed'
              AND pe.probe_status = 'passed'
            ORDER BY pe.provider_model_id
            """
        ).fetchall()
        latest_metrics = _latest_aa_metrics_by_model(transaction)
        latest_health = _latest_health_by_endpoint(transaction)
        pool_remaining = _latest_remaining_by_pool(transaction)
        written = 0
        for role in roles:
            requirements = role["requirements"] or {}
            required = set(requirements.get("capabilities", []))
            for endpoint in endpoints:
                remaining = pool_remaining.get(
                    str(endpoint["quota_pool_id"]), _remaining_amount(endpoint["effective_remaining"])
                )
                eligibility = eligible_for_scoring(
                    {
                        "access": "free_quota_available",
                        "basic_probe": endpoint["probe_status"] == "passed",
                        "quota": remaining,
                        "matched": True,
                        "breaker": "closed",
                        "capabilities": set((endpoint["capabilities"] or {}).keys()),
                    },
                    required_capabilities=required,
                )
                if eligibility.eligible:
                    eligibility = _context_window_eligibility(endpoint, requirements)
                if eligibility.eligible:
                    eligibility = _quality_gate_eligibility(
                        role, latest_metrics.get(endpoint["canonical_model_id"]), requirements
                    )
                metrics_row = latest_metrics.get(endpoint["canonical_model_id"], {})
                benchmark = aa_subscore(
                    metrics_row.get("metrics", {}),
                    weights=AA_SCORE_WEIGHTS,
                    percentiles=AA_SCORE_PERCENTILES,
                )
                health = latest_health.get(str(endpoint["id"]), {})
                endpoint_p95 = health.get("endpoint_p95")
                provider_p95 = health.get("provider_p95")
                latency = latency_score_source(
                    endpoint_p95=int(endpoint_p95) if isinstance(endpoint_p95, int | float) else None,
                    provider_p95=int(provider_p95) if isinstance(provider_p95, int | float) else None,
                    aa_latency=metrics_row.get("aa_latency"),
                )
                score = score_endpoint(
                    {
                        "benchmark_fit": benchmark.value or 0.0,
                        "capability_fit": 1.0 if eligibility.eligible else 0.0,
                        "health": float(health.get("health") or 0.0),
                        "latency": _latency_component(*latency),
                        "quota_headroom": min(remaining / 100, 1.0),
                        "stability": float(health.get("stability") or 0.0),
                        "uncertainty": benchmark.uncertainty_penalty + (0.1 if benchmark.unknown else 0.0),
                    }
                )
                context.repository.scores.upsert(
                    transaction,
                    role_id=role["id"],
                    endpoint_id=endpoint["id"],
                    score_version="production-v1",
                    total_score=score.total,
                    component_scores=score.components,
                    eligibility=eligibility.eligible,
                    rejection_reasons=[] if eligibility.eligible else [eligibility.reason or "unknown"],
                    input_state_hash=_hash_parts(str(role["id"]), str(endpoint["id"]), str(score.total)),
                )
                written += 1
    return _effect_result("role-scoring", changed=written > 0)


def _seed_quality_bands(transaction: Any, client: Any) -> None:
    current = _read_current_combos(client)
    latest_metrics = _latest_aa_metrics_by_model(transaction)
    for combo_id, members in current.items():
        if not combo_id.startswith("fmo-") or len(members) != 1:
            continue
        # AICODE-NOTE: A live one-member combo is the operator seed signal; a
        # multi-member combo keeps its persisted band to avoid drift per run.
        role_id = combo_id.removeprefix("fmo-")
        seed = transaction.execute(
            """
            SELECT id, canonical_model_id
            FROM provider_endpoints
            WHERE id::text = %(endpoint_id)s
            """,
            {"endpoint_id": str(members[0])},
        ).fetchone()
        if seed is None:
            continue
        metric = "intelligence_index"
        metrics = latest_metrics.get(seed["canonical_model_id"])
        if not metrics or metric not in metrics["metrics"]:
            continue
        anchor = float(metrics["metrics"][metric])
        candidates = _quality_band_candidates(transaction, metric)
        protected = _latest_protected_requests(transaction, role_id)
        band = quality_band_for_demand(
            anchor=anchor,
            candidates=candidates,
            protected_requests=protected,
            adequacy_floor=max(0, anchor - 20),
        )
        transaction.execute(
            """
            UPDATE roles
            SET minimum_quality_metric = %(metric)s,
                minimum_quality_value = %(minimum)s,
                maximum_quality_metric = %(metric)s,
                maximum_quality_value = %(maximum)s,
                quality_gate_index_version = %(index_version)s
            WHERE id = %(role_id)s
            """,
            {
                "role_id": role_id,
                "metric": metric,
                "minimum": band.minimum,
                "maximum": band.maximum,
                "index_version": str(metrics["index_version"]),
            },
        )


def _quality_band_candidates(transaction: Any, metric: str) -> list[dict[str, Any]]:
    rows = transaction.execute(
        f"""
        SELECT aa.{metric} AS quality, eas.effective_remaining, eas.status, eas.hard_stop_capable
        FROM provider_endpoints pe
        JOIN artificial_analysis_model_metrics aa ON aa.canonical_model_id = pe.canonical_model_id
        LEFT JOIN endpoint_access_states eas ON eas.endpoint_id = pe.id
        WHERE aa.{metric} IS NOT NULL
        """
    ).fetchall()
    return [
        {
            "quality": float(row["quality"]),
            "capacity": _remaining_requests(row["effective_remaining"])
            if row["effective_remaining"] is not None
            else 0,
            "confirmed_free": row["status"] == "confirmed" and bool(row["hard_stop_capable"]),
        }
        for row in rows
    ]


def _latest_protected_requests(transaction: Any, role_id: str) -> float:
    row = transaction.execute(
        """
        SELECT protected_requests
        FROM role_demand_forecasts
        WHERE role_id = %(role_id)s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        {"role_id": role_id},
    ).fetchone()
    return float(row["protected_requests"]) if row is not None else 1.0


def _latest_aa_metrics_by_model(transaction: Any) -> dict[Any, dict[str, Any]]:
    rows = transaction.execute(
        """
        SELECT DISTINCT ON (canonical_model_id)
               canonical_model_id, intelligence_index, coding_index, agentic_index,
               median_end_to_end_seconds, index_version
        FROM artificial_analysis_model_metrics
        ORDER BY canonical_model_id, fetched_at DESC
        """
    ).fetchall()
    return {
        row["canonical_model_id"]: {
            "metrics": {
                key: float(row[key])
                for key in ("intelligence_index", "coding_index", "agentic_index")
                if row[key] is not None
            },
            "index_version": row["index_version"],
            "aa_latency": float(row["median_end_to_end_seconds"])
            if row["median_end_to_end_seconds"] is not None
            else None,
        }
        for row in rows
    }


def _latest_health_by_endpoint(transaction: Any) -> dict[str, dict[str, float | int | None]]:
    rows = transaction.execute(
        """
        SELECT pe.id AS endpoint_id, endpoint.status AS endpoint_status,
               endpoint.latency_p95_ms AS endpoint_p95, provider.latency_p95_ms AS provider_p95,
               endpoint.success_rate AS endpoint_success_rate, endpoint.error_rate AS endpoint_error_rate,
               endpoint.sample_count AS endpoint_sample_count
        FROM provider_endpoints pe
        JOIN provider_accounts pa ON pa.id = pe.provider_account_id
        LEFT JOIN LATERAL (
          SELECT status, latency_p95_ms, success_rate, error_rate, sample_count
          FROM endpoint_health_observations
          WHERE endpoint_id = pe.id
          ORDER BY observed_at DESC
          LIMIT 1
        ) endpoint ON true
        LEFT JOIN LATERAL (
          SELECT latency_p95_ms
          FROM endpoint_health_observations
          WHERE provider_id = pa.provider_id
            AND endpoint_id IS NULL
          ORDER BY observed_at DESC
          LIMIT 1
        ) provider ON true
        ORDER BY pe.id
        """
    ).fetchall()
    return {
        str(row["endpoint_id"]): {
            "health": _health_component(
                row["endpoint_status"], row["endpoint_success_rate"], row["endpoint_error_rate"]
            ),
            "stability": _stability_component(row["endpoint_status"], row["endpoint_sample_count"]),
            "endpoint_p95": row["endpoint_p95"],
            "provider_p95": row["provider_p95"],
        }
        for row in rows
    }


def _latest_remaining_by_pool(transaction: Any) -> dict[str, float]:
    rows = transaction.execute(
        """
        SELECT DISTINCT ON (quota_pool_id) quota_pool_id, remaining_value
        FROM quota_observations
        WHERE metric = 'requests'
          AND remaining_value IS NOT NULL
        ORDER BY quota_pool_id, observed_at DESC
        """
    ).fetchall()
    return {str(row["quota_pool_id"]): float(row["remaining_value"]) for row in rows}


def _health_component(status: str | None, success_rate: Any, error_rate: Any) -> float:
    # success_rate / error_rate are stored as fractions in [0, 1] by
    # _insert_health_observation (1 - failure/requests), not percentages.
    if success_rate is not None:
        return max(0.0, min(float(success_rate), 1.0))
    if error_rate is not None:
        return max(0.0, min(1.0 - float(error_rate), 1.0))
    if status == "active":
        return 0.9
    if status == "degraded":
        return 0.35
    return 0.0


def _stability_component(status: str | None, sample_count: Any) -> float:
    if status == "active":
        base = 0.9
    elif status == "degraded":
        base = 0.35
    else:
        base = 0.0
    if sample_count is None:
        return base
    return min(base, max(0.0, float(sample_count) / 10.0))


def _latency_component(source: str, value: float | None) -> float:
    if value is None:
        return 0.0
    latency_ms = float(value) * 1000.0 if source == "aa" else float(value)
    return max(0.0, min(1.0, 1.0 - latency_ms / 10_000.0))


def _context_window_eligibility(endpoint: Any, requirements: dict[str, Any]) -> EligibilityDecision:
    minimum = requirements.get("minimum_context_window")
    if minimum is None:
        return EligibilityDecision(True)
    effective = effective_context_window(
        [
            endpoint["advertised_context_window"],
            endpoint["provider_context_window"],
            endpoint["probed_context_window"],
            endpoint["effective_context_window"],
        ]
    )
    decision = context_eligible(
        effective_context=effective,
        minimum_context=int(minimum),
        manual_override=bool(requirements.get("manual_context_override", False)),
    )
    if decision.eligible:
        return EligibilityDecision(True)
    return EligibilityDecision(False, "context")


def _quality_gate_eligibility(
    role: Any, metrics_row: dict[str, Any] | None, requirements: dict[str, Any]
) -> EligibilityDecision:
    if role["minimum_quality_metric"] is None or role["minimum_quality_value"] is None:
        return EligibilityDecision(True)
    current_version = metrics_row.get("index_version") if metrics_row else role["quality_gate_index_version"]
    decision = evaluate_quality_gate(
        (metrics_row or {}).get("metrics", {}),
        metric=role["minimum_quality_metric"],
        value=float(role["minimum_quality_value"]),
        maximum_value=float(role["maximum_quality_value"]) if role["maximum_quality_value"] is not None else None,
        index_version=str(role["quality_gate_index_version"]),
        current_version=str(current_version),
        allow_unverified=bool(requirements.get("allow_unverified_quality_gate", False)),
    )
    if decision.eligible:
        return EligibilityDecision(True)
    return EligibilityDecision(False, f"quality_gate:{decision.status}")


def _roles_needing_quality_recalibration(transaction: Any) -> set[str]:
    rows = transaction.execute(
        """
        SELECT DISTINCT ON (role_id) role_id, rejection_reasons
        FROM role_scores
        WHERE rejection_reasons @> '["quality_gate:needs_recalibration"]'::jsonb
        ORDER BY role_id, calculated_at DESC
        """
    ).fetchall()
    return {row["role_id"] for row in rows}


def _insert_health_observation(
    transaction: Any,
    *,
    provider_id: Any | None,
    endpoint_id: Any | None,
    status: str,
    metric: Any,
    observed_at: datetime,
) -> None:
    success_rate = None
    error_rate = None
    if metric.requests:
        error_rate = metric.failure_count / metric.requests
        success_rate = 1 - error_rate
    transaction.execute(
        """
        INSERT INTO endpoint_health_observations (
          endpoint_id, provider_id, granularity, status, success_rate, error_rate,
          latency_p50_ms, latency_p95_ms, sample_count, observed_at
        )
        VALUES (
          %(endpoint_id)s, %(provider_id)s, %(granularity)s, %(status)s,
          %(success_rate)s, %(error_rate)s, %(latency_p50_ms)s, %(latency_p95_ms)s,
          %(sample_count)s, %(observed_at)s
        )
        """,
        {
            "endpoint_id": endpoint_id,
            "provider_id": provider_id,
            "granularity": metric.latency_granularity,
            "status": status,
            "success_rate": success_rate,
            "error_rate": error_rate,
            "latency_p50_ms": metric.avg_latency_ms,
            "latency_p95_ms": metric.p95_ms,
            "sample_count": metric.requests,
            "observed_at": observed_at,
        },
    )


def _latest_role_diagnostic(transaction: Any, role_id: str) -> dict[str, Any] | None:
    row = transaction.execute(
        """
        SELECT r.id AS role_id, ap.status, ap.targets, ap.constraint_report
        FROM roles r
        LEFT JOIN allocation_plans ap ON ap.role_id = r.id
        WHERE r.id = %(role_id)s
        ORDER BY ap.created_at DESC NULLS LAST
        LIMIT 1
        """,
        {"role_id": role_id},
    ).fetchone()
    return dict(row) if row is not None else None
