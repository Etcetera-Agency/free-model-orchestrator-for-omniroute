import pytest

from fmo.allocation import (
    allocate_globally,
    build_priority_combo,
    keep_stable_order,
    validate_plan,
)
from fmo.applier import ComboApplier, ComboConflict
from fmo.audit import audit_change, rollback_run
from fmo.forecast import (
    aggregate_demand,
    apply_historical_reserve,
    cold_start_demand,
    protected_demand,
    quality_band_for_demand,
)


@pytest.mark.spec("demand-forecast::Multiple agents and a shared role")
@pytest.mark.spec("demand-forecast::Dependency cycle")
def test_demand_aggregation_expands_shared_role_dag_and_rejects_cycle():
    demand = aggregate_demand(
        agent_runs={"a": 20, "b": 10, "c": 5},
        bindings=[("a", "research_scout", 1), ("b", "research_scout", 1), ("c", "research_scout", 1)],
        dependencies=[("research_scout", "fetch", 3)],
    )
    assert demand["research_scout"] == 35
    assert demand["fetch"] == 105

    with pytest.raises(ValueError):
        aggregate_demand(
            {"a": 1}, [("a", "fetch", 1)], [("fetch", "research_scout", 1), ("research_scout", "fetch", 1)]
        )


@pytest.mark.spec("demand-forecast::Reserve applied once")
@pytest.mark.spec("demand-forecast::Unknown new role")
@pytest.mark.spec("demand-forecast::Bursty weekly load")
def test_protected_demand_reserve_once_and_cold_start_priority():
    assert protected_demand(expected=10, p95=25, peak_multiplier=2) == 25
    reserved = apply_historical_reserve(100, multiplier=1.2, already_applied=False)
    assert reserved.base == 100
    assert reserved.reserved == 120
    assert apply_historical_reserve(reserved.reserved, multiplier=1.2, already_applied=True).reserved == 120
    assert cold_start_demand(schedule=None, bootstrap=None, role_minimum=10, global_minimum=5).value == 10


@pytest.mark.spec("allocator::Shared endpoint across roles")
def test_global_allocation_shared_capacity_and_heavy_role_separation():
    plan = allocate_globally(
        roles=["research_scout", "health_reasoning", "routing_fast"],
        endpoints=[
            {"id": "e1", "pool": "pool-a", "score": 100, "capacity": 100},
            {"id": "e2", "pool": "pool-b", "score": 90, "capacity": 100},
        ],
        demand={"research_scout": 60, "health_reasoning": 60, "routing_fast": 20},
    )
    assert plan.allocations["research_scout"].pool != plan.allocations["health_reasoning"].pool
    assert plan.pool_usage["pool-a"] <= 100


@pytest.mark.spec("allocator::Combo output")
@pytest.mark.spec("allocator::Combo orders weakest-eligible first")
def test_priority_combo_no_weights_oversubscription_and_degraded_modes():
    combo = build_priority_combo(
        "research_scout",
        [{"id": "e1", "score": 2}, {"id": "e2", "score": 1}],
        per_pool_cap=2,
        demand=0,
        pool_usage={},
        reserved_endpoint_id=None,
    )
    blocked = validate_plan({"pool-a": {"usage": 120, "capacity": 100}})
    degraded = validate_plan({"pool-a": {"usage": 0, "capacity": 0}}, role_has_primary=False)
    assert combo.strategy == "priority"
    assert combo.weights is None
    assert combo.endpoints == ["e2", "e1"]
    assert blocked.apply is False
    assert blocked.reason == "oversubscribed"
    assert degraded.role_status == "unavailable"


def _router_endpoint(endpoint_id: str, **overrides):
    endpoint = {
        "id": endpoint_id,
        "is_router": True,
        "access": "free_quota_available",
        "basic_probe": True,
        "quota": 100,
        "breaker": "closed",
        "input": ("text",),
        "effective_context_window": 128_000,
    }
    endpoint.update(overrides)
    return endpoint


@pytest.mark.spec("allocator::Router never outranks a scored endpoint")
@pytest.mark.spec("allocator::Configured routers pinned to the tail in config order")
def test_priority_combo_appends_configured_router_tail_after_scored_head():
    combo = build_priority_combo(
        "routing_fast",
        [
            {"id": "scored-a", "score": 2},
            {"id": "scored-b", "score": 1},
            _router_endpoint("openrouter/free", input=("text", "image")),
            _router_endpoint("mimocode/mimo-auto"),
        ],
        per_pool_cap=2,
        demand=0,
        pool_usage={},
        reserved_endpoint_id=None,
        auto_router_tail=("mimocode/mimo-auto", "openrouter/free"),
        required_capabilities={"text"},
    )

    assert combo.endpoints == ["scored-b", "scored-a", "mimocode/mimo-auto", "openrouter/free"]


@pytest.mark.spec("allocator::Router skipped when its declared modalities miss a role capability")
@pytest.mark.spec("allocator::Router skipped when its effective context is below the role minimum")
@pytest.mark.spec("role-scorer::Router still honors non-quality filters")
def test_priority_combo_filters_router_tail_by_role_and_access_constraints():
    combo = build_priority_combo(
        "vision_role",
        [
            _router_endpoint("text-only", input=("text",)),
            _router_endpoint("short-context", input=("text", "image"), effective_context_window=8_000),
            _router_endpoint("paid-router", input=("text", "image"), access="paid_only_excluded"),
            _router_endpoint("openrouter/free", input=("text", "image"), effective_context_window=128_000),
        ],
        per_pool_cap=2,
        demand=0,
        pool_usage={},
        reserved_endpoint_id=None,
        auto_router_tail=("text-only", "short-context", "paid-router", "openrouter/free"),
        required_capabilities={"image"},
        minimum_context=64_000,
    )

    assert combo.endpoints == ["openrouter/free"]


@pytest.mark.spec("allocator::Router-only combo is allowed")
def test_priority_combo_allows_router_only_combo_when_no_scored_endpoint_eligible():
    combo = build_priority_combo(
        "routing_fast",
        [_router_endpoint("mimocode/mimo-auto"), _router_endpoint("openrouter/free", input=("text", "image"))],
        per_pool_cap=2,
        demand=0,
        pool_usage={},
        reserved_endpoint_id=None,
        auto_router_tail=("mimocode/mimo-auto", "openrouter/free"),
        required_capabilities={"text"},
    )

    assert combo.endpoints == ["mimocode/mimo-auto", "openrouter/free"]


@pytest.mark.spec("allocator::Zero capacity pool")
def test_validate_plan_zero_capacity_pool_is_oversubscribed():
    blocked = validate_plan({"pool-a": {"usage": 1, "capacity": 0}})

    assert blocked.apply is False
    assert blocked.reason == "oversubscribed"


@pytest.mark.spec("allocator::No endpoint with capacity")
def test_allocation_omits_role_when_no_endpoint_has_capacity():
    plan = allocate_globally(
        roles=["routing_fast"],
        endpoints=[
            {"id": "e1", "pool": "pool-a", "score": 100, "capacity": 5},
            {"id": "e2", "pool": "pool-b", "score": 90, "capacity": 9},
        ],
        demand={"routing_fast": 10},
    )

    assert "routing_fast" not in plan.allocations


@pytest.mark.spec("allocator::Heavy role same pool second primary")
def test_heavy_role_priority_combo_skips_second_primary_in_same_pool():
    combo = build_priority_combo(
        "research_scout",
        [
            {"id": "e1", "pool": "pool-a", "score": 100, "capacity": 1},
            {"id": "e2", "pool": "pool-a", "score": 99, "capacity": 1},
            {"id": "e3", "pool": "pool-b", "score": 98, "capacity": 1},
        ],
        per_pool_cap=2,
        demand=0,
        pool_usage={},
        reserved_endpoint_id=None,
    )

    assert combo.endpoints == ["e3", "e2"]


@pytest.mark.spec("allocator::Fallback members reserve their pool capacity")
def test_priority_combo_reserves_fallback_member_capacity():
    pool_usage = {}

    combo = build_priority_combo(
        "routing_fast",
        [
            {"id": "primary", "pool": "pool-a", "score": 10, "capacity": 20},
            {"id": "fallback", "pool": "pool-a", "score": 9, "capacity": 20},
        ],
        per_pool_cap=2,
        demand=10,
        pool_usage=pool_usage,
        reserved_endpoint_id=None,
    )

    assert combo.endpoints == ["fallback", "primary"]
    assert pool_usage["pool-a"] == 20


@pytest.mark.spec("allocator::Combo member without pool capacity is dropped")
def test_priority_combo_drops_member_without_pool_capacity():
    pool_usage = {"pool-a": 10}

    combo = build_priority_combo(
        "routing_fast",
        [
            {"id": "blocked", "pool": "pool-a", "score": 9, "capacity": 10},
            {"id": "available", "pool": "pool-b", "score": 8, "capacity": 20},
        ],
        per_pool_cap=2,
        demand=10,
        pool_usage=pool_usage,
        reserved_endpoint_id=None,
    )

    assert combo.endpoints == ["available"]
    assert pool_usage == {"pool-a": 10, "pool-b": 10}


@pytest.mark.spec("demand-forecast::Quality band widens to cover protected demand")
def test_quality_band_widens_until_confirmed_free_capacity_covers_demand():
    band = quality_band_for_demand(
        anchor=60,
        candidates=[
            {"quality": 60, "capacity": 10, "confirmed_free": True},
            {"quality": 50, "capacity": 20, "confirmed_free": True},
            {"quality": 70, "capacity": 30, "confirmed_free": True},
            {"quality": 30, "capacity": 100, "confirmed_free": True},
            {"quality": 65, "capacity": 100, "confirmed_free": False},
        ],
        protected_requests=55,
        adequacy_floor=45,
    )
    degraded = quality_band_for_demand(
        anchor=60,
        candidates=[{"quality": 50, "capacity": 5, "confirmed_free": True}],
        protected_requests=20,
        adequacy_floor=45,
    )

    assert band.minimum == 50
    assert band.maximum == 70
    assert band.degraded is False
    assert degraded.degraded is True


@pytest.mark.spec("role-scorer::Unchanged inputs")
def test_stability_keeps_order_for_subthreshold_drift():
    current = ["e1", "e2"]
    assert keep_stable_order(current, {"e1": 1.0, "e2": 1.01}, threshold=0.05) == current


@pytest.mark.spec("allocator::Missing score during stable order")
def test_stability_tolerates_missing_score_for_previous_endpoint():
    current = ["e1", "e2"]

    assert keep_stable_order(current, {"e2": 1.0}, threshold=0.05) == current


@pytest.mark.spec("combo-applier::Foreign combo")
@pytest.mark.spec("combo-applier::State changed under us")
@pytest.mark.spec("combo-applier::Smoke test fails")
@pytest.mark.spec("combo-applier::Manual edit detected")
@pytest.mark.spec("combo-applier::Failing guard input blocks apply")
@pytest.mark.spec("combo-applier::Healthy guard inputs allow apply")
@pytest.mark.spec("combo-applier::Non-existent combo is not created")
def test_applier_manages_only_fmo_transaction_smoke_rollback_and_drift():
    applier = ComboApplier(current={"fmo-role": ["old"], "foreign": ["x"]})
    assert applier.managed_names() == ["fmo-role"]
    applier.apply("fmo-role", ["new"], expected_hash=applier.state_hash("fmo-role"), smoke_ok=True)
    assert applier.current["fmo-role"] == ["new"]
    with pytest.raises(ComboConflict):
        applier.apply("fmo-missing", ["new"], expected_hash=applier.state_hash("fmo-missing"), smoke_ok=True)
    with pytest.raises(ComboConflict):
        applier.apply("fmo-role", ["other"], expected_hash="stale", smoke_ok=True)
    applier.apply("fmo-role", ["bad"], expected_hash=applier.state_hash("fmo-role"), smoke_ok=False)
    assert applier.current["fmo-role"] == ["new"]
    assert applier.run_status == "failed"


@pytest.mark.spec("audit-rollback::Combo change logged")
@pytest.mark.spec("audit-rollback::Roll back a run")
@pytest.mark.spec("audit-rollback::Inspect an assignment")
def test_audit_change_log_and_rollback_run():
    log = []
    audit_change(
        log,
        run_id="r1",
        entity_type="combo",
        entity_id="fmo-role",
        before=["a"],
        after=["b"],
        reasons=["score"],
        sources=["plan"],
    )
    restored = rollback_run(log, run_id="r1", catalog_snapshots=["keep"])
    assert log[0]["before_json"] == ["a"]
    assert restored["fmo-role"] == ["a"]
    assert restored["catalog_snapshots"] == ["keep"]
