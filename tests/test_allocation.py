import pytest

from fmo.allocation import (
    allocate_globally,
    build_priority_combo,
    keep_stable_order,
    validate_plan,
)
from fmo.applier import ComboApplier, ComboConflict
from fmo.audit import audit_change, rollback_run
from fmo.forecast import aggregate_demand, apply_historical_reserve, cold_start_demand, protected_demand


def test_demand_aggregation_expands_shared_role_dag_and_rejects_cycle():
    demand = aggregate_demand(
        agent_runs={"a": 20, "b": 10, "c": 5},
        bindings=[("a", "research_scout", 1), ("b", "research_scout", 1), ("c", "research_scout", 1)],
        dependencies=[("research_scout", "fetch", 3)],
    )
    assert demand["research_scout"] == 35
    assert demand["fetch"] == 105

    with pytest.raises(ValueError):
        aggregate_demand({"a": 1}, [("a", "fetch", 1)], [("fetch", "research_scout", 1), ("research_scout", "fetch", 1)])


def test_protected_demand_reserve_once_and_cold_start_priority():
    assert protected_demand(expected=10, p95=25, peak_multiplier=2) == 25
    reserved = apply_historical_reserve(100, multiplier=1.2, already_applied=False)
    assert reserved.base == 100
    assert reserved.reserved == 120
    assert apply_historical_reserve(reserved.reserved, multiplier=1.2, already_applied=True).reserved == 120
    assert cold_start_demand(schedule=None, bootstrap=None, role_minimum=10, global_minimum=5).value == 10


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


def test_priority_combo_no_weights_oversubscription_and_degraded_modes():
    combo = build_priority_combo("research_scout", [{"id": "e1", "score": 2}, {"id": "e2", "score": 1}], per_pool_cap=2)
    blocked = validate_plan({"pool-a": {"usage": 120, "capacity": 100}})
    degraded = validate_plan({"pool-a": {"usage": 0, "capacity": 0}}, role_has_primary=False)
    assert combo.strategy == "priority"
    assert combo.weights is None
    assert combo.endpoints == ["e1", "e2"]
    assert blocked.apply is False
    assert blocked.reason == "oversubscribed"
    assert degraded.role_status == "unavailable"


def test_stability_keeps_order_for_subthreshold_drift():
    current = ["e1", "e2"]
    assert keep_stable_order(current, {"e1": 1.0, "e2": 1.01}, threshold=0.05) == current


def test_applier_manages_only_fmo_transaction_smoke_rollback_and_drift():
    applier = ComboApplier(current={"fmo-role": ["old"], "foreign": ["x"]})
    assert applier.managed_names() == ["fmo-role"]
    applier.apply("fmo-role", ["new"], expected_hash=applier.state_hash("fmo-role"), smoke_ok=True)
    assert applier.current["fmo-role"] == ["new"]
    with pytest.raises(ComboConflict):
        applier.apply("fmo-role", ["other"], expected_hash="stale", smoke_ok=True)
    applier.apply("fmo-role", ["bad"], expected_hash=applier.state_hash("fmo-role"), smoke_ok=False)
    assert applier.current["fmo-role"] == ["new"]
    assert applier.run_status == "failed"


def test_audit_change_log_and_rollback_run():
    log = []
    audit_change(log, run_id="r1", entity_type="combo", entity_id="fmo-role", before=["a"], after=["b"], reasons=["score"], sources=["plan"])
    restored = rollback_run(log, run_id="r1", catalog_snapshots=["keep"])
    assert log[0]["before_json"] == ["a"]
    assert restored["fmo-role"] == ["a"]
    assert restored["catalog_snapshots"] == ["keep"]
