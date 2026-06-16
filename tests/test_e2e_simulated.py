from datetime import datetime, timedelta, timezone

import pytest

from fmo.access import classify_access
from fmo.allocation import allocate_globally, build_priority_combo, validate_plan
from fmo.applier import ComboApplier, ComboConflict
from fmo.audit import audit_change, rollback_run
from fmo.candidates import build_free_candidates
from fmo.cli import run_cli
from fmo.context import context_eligible, effective_context_window
from fmo.forecast import aggregate_demand, protected_demand
from fmo.matcher import match_model
from fmo.probes import probe_endpoint, should_probe
from fmo.quality import evaluate_quality_gate
from fmo.quota_manager import effective_remaining
from fmo.quota_research import QuotaClaim, activate_summary_rule
from fmo.registry import sync_free_registry
from fmo.scoring import eligible_for_scoring, score_endpoint
from fmo.smart_review import apply_review_diffs, run_combo_review
from fmo.web_cookie import source_web_cookie_endpoints, web_cookie_allocation_policy


class SimProbeClient:
    def __init__(self):
        self.calls = []

    def post(self, path, payload, headers=None):
        self.calls.append((path, payload, headers or {}))
        return {"status_code": 200, "content": "ok", "model": payload["model"]}


def test_simulated_daily_batch_builds_and_applies_free_combo():
    candidates = build_free_candidates(
        {
            "providers": {
                "free-provider": {
                    "models": {
                        "free-chat": {
                            "name": "Free Chat",
                            "cost": {"input": 0, "output": 0},
                        }
                    }
                }
            }
        }
    )
    registry = sync_free_registry(
        {
            "models": [
                {
                    "provider": "free-provider",
                    "modelId": "free-chat",
                    "displayName": "Free Chat",
                    "monthlyTokens": 10_000,
                    "poolKey": "free-provider:pool",
                    "authType": "none",
                }
            ]
        }
    )
    claim = QuotaClaim(metric="requests", amount=100, window="day", evidence=["search summary"], hard_stop=True)
    rule = activate_summary_rule(claim, summary_confidence_cap=0.7)
    access = classify_access(
        {
            "quota_rule": True,
            "limit": rule.claim.amount,
            "remaining": 90,
            "reset_at": datetime.now(timezone.utc) + timedelta(hours=12),
            "hard_stop": True,
        }
    )
    remaining = effective_remaining(limit=100, provider_remaining=90, local_used=5, pending_reserved=1, safety_buffer=4)

    probe_client = SimProbeClient()
    assert should_probe(access.status, reserved_capacity=True)
    probe = probe_endpoint(probe_client, provider="free-provider", model="free-chat", capabilities={"tools": False})
    match = match_model("free-provider/free-chat", canonical_slugs={"free-chat"}, provider_catalog_ids={"free-provider/free-chat"})
    context = context_eligible(
        effective_context=effective_context_window([128_000, 64_000]),
        minimum_context=32_000,
    )
    quality = evaluate_quality_gate(
        {"intelligence_index": 50},
        metric="intelligence_index",
        value=40,
        index_version="v1",
        current_version="v1",
    )
    endpoint = {
        "access": access.status,
        "basic_probe": probe.passed,
        "quota": remaining,
        "matched": match.auto_use,
        "breaker": "closed",
        "capabilities": {"text_chat"},
    }
    eligibility = eligible_for_scoring(endpoint, required_capabilities={"text_chat"})
    score = score_endpoint(
        {
            "benchmark_fit": 1,
            "capability_fit": 1,
            "health": 1,
            "latency": 1,
            "quota_headroom": 1,
            "stability": 1,
        }
    )
    demand = aggregate_demand({"agent": 5}, [("agent", "routing_fast", 1)], [])
    demand["routing_fast"] = protected_demand(expected=demand["routing_fast"], p95=6, peak_multiplier=1.2)
    plan = allocate_globally(
        roles=["routing_fast"],
        endpoints=[{"id": "free-provider/free-chat", "pool": "free-provider:pool", "score": score.total, "capacity": remaining}],
        demand=demand,
    )
    combo = build_priority_combo("routing_fast", [{"id": plan.allocations["routing_fast"].endpoint_id, "score": score.total}], per_pool_cap=2)
    reviewed_combo, review_audit = apply_review_diffs(
        {"routing_fast": combo.endpoints},
        [{"op": "move", "role": "routing_fast", "endpoint_id": "free-provider/free-chat", "position": 0}],
        candidate_registry=set(combo.endpoints),
        minimum_combo_size=1,
    )
    validation = validate_plan({"free-provider:pool": {"usage": demand["routing_fast"], "capacity": remaining}})
    applier = ComboApplier(current={"fmo-role-routing-fast": ["old"]})
    before_hash = applier.state_hash("fmo-role-routing-fast")
    applier.apply("fmo-role-routing-fast", reviewed_combo["routing_fast"], expected_hash=before_hash, smoke_ok=True)
    log = []
    audit_change(
        log,
        run_id="run-1",
        entity_type="combo",
        entity_id="fmo-role-routing-fast",
        before=["old"],
        after=reviewed_combo["routing_fast"],
        reasons=["simulated_e2e"],
        sources=["tests/test_e2e_simulated.py"],
    )

    assert ("free-provider", "free-chat") in candidates
    assert ("free-provider", "free-chat") in registry.models
    assert access.status == "free_quota_available"
    assert context.eligible is True
    assert quality.eligible is True
    assert eligibility.eligible is True
    assert validation.apply is True
    assert review_audit["rejected"] == []
    assert applier.current["fmo-role-routing-fast"] == ["free-provider/free-chat"]
    assert applier.run_status == "committed"
    assert log[0]["after_json"] == ["free-provider/free-chat"]


def test_simulated_e2e_failure_paths_fail_closed_without_paid_or_combo_test():
    web_cookie = source_web_cookie_endpoints(
        connections=[{"id": "cookie-1", "auth_type": "web_cookie", "model": "browser-only"}],
        static=[],
        manual=[],
        previous=[],
        daily_refresh=True,
    )
    policy = web_cookie_allocation_policy(quota_known=False, primary_override=False)
    access = classify_access({"models_dev_free": True, "live_paid_charge": True})
    review = run_combo_review(
        lambda payload: {"diffs": [{"op": "strategy", "role": "routing_fast", "endpoint_id": "cookie-1"}]},
        deterministic_combo={"routing_fast": ["safe-free"]},
        trigger=True,
    )
    applier = ComboApplier(current={"fmo-role-routing-fast": ["safe-free"]})

    with pytest.raises(ComboConflict):
        applier.apply("fmo-role-routing-fast", ["cookie-1"], expected_hash="stale", smoke_ok=True)

    cli_result = run_cli(["apply"], preconditions_ok=False)
    rollback = rollback_run(
        [
            {
                "run_id": "run-1",
                "entity_type": "combo",
                "entity_id": "fmo-role-routing-fast",
                "before_json": ["safe-free"],
            }
        ],
        run_id="run-1",
        catalog_snapshots=["snapshot-kept"],
    )

    assert web_cookie[0].auto_discovered is False
    assert policy.budget_type == "opportunistic"
    assert policy.guaranteed_capacity == 0
    assert access.status == "paid_only_excluded"
    assert review.valid_diffs == []
    assert review.combo_test_called is False
    assert cli_result.exit_code == 5
    assert cli_result.changed is False
    assert rollback["fmo-role-routing-fast"] == ["safe-free"]
    assert rollback["catalog_snapshots"] == ["snapshot-kept"]
