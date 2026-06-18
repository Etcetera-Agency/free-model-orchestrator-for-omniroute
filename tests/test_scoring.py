import pytest

from fmo.context import context_eligible, effective_context_window
from fmo.probes import handle_probe_error, probe_endpoint, should_probe
from fmo.quality import evaluate_quality_gate
from fmo.scoring import (
    _normalize,
    aa_subscore,
    eligible_for_scoring,
    latency_score_source,
    score_endpoint,
    should_recompute_score,
)
from fmo.telemetry import degrade_endpoint, normalize_latency


class ProbeClient:
    def __init__(self, status_code=200, content="ok"):
        self.status_code = status_code
        self.content = content
        self.calls = []

    def post(self, path, payload, headers=None):
        self.calls.append((path, payload, headers or {}))
        return {"status_code": self.status_code, "content": self.content, "model": payload["model"]}


@pytest.mark.spec("probe-runner::No reserved capacity")
def test_probe_runs_only_after_free_classification_and_reserved_capacity():
    assert should_probe("unknown_excluded", reserved_capacity=True) is False
    assert should_probe("free_quota_available", reserved_capacity=False) is False
    assert should_probe("free_unlimited", reserved_capacity=True) is True


@pytest.mark.spec("probe-runner::Unclaimed capability")
def test_probe_uses_dedicated_route_no_cache_and_capability_suites():
    client = ProbeClient()
    result = probe_endpoint(client, provider="p", model="m", capabilities={"tools": False, "vision": True})

    assert client.calls[0][0] == "/v1/providers/p/chat/completions"
    assert client.calls[0][1]["model"] == "m"
    assert client.calls[0][2]["X-OmniRoute-No-Cache"] == "true"
    assert result.suites == ("basic_text", "vision")


def test_probe_error_map_and_promotion_preconditions():
    assert handle_probe_error(402) == ("exclude", "quota_research")
    assert handle_probe_error(429) == ("quota_manager", "no_retry")
    assert handle_probe_error(401) == ("auth_degraded", "no_retry")
    assert handle_probe_error(500) == ("retry", "provider_5xx")


@pytest.mark.spec("probe-runner::Probe error table")
@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (402, ("exclude", "quota_research")),
        (429, ("quota_manager", "no_retry")),
        (401, ("auth_degraded", "no_retry")),
        (403, ("auth_degraded", "no_retry")),
        (500, ("retry", "provider_5xx")),
        (418, ("failed", "unknown")),
    ],
)
def test_probe_error_table(status_code, expected):
    assert handle_probe_error(status_code) == expected


@pytest.mark.spec("probe-runner::Non-200 or empty content")
@pytest.mark.parametrize("client", [ProbeClient(status_code=500), ProbeClient(content="")])
def test_probe_endpoint_fails_on_non_200_or_empty_content(client):
    result = probe_endpoint(client, provider="p", model="m", capabilities={})

    assert result.passed is False


@pytest.mark.spec("telemetry-sync::Only provider-level latency")
@pytest.mark.spec("telemetry-sync::Consecutive failures")
@pytest.mark.spec("role-scorer::Endpoint telemetry available")
def test_telemetry_granularity_and_degradation_is_endpoint_scoped():
    latency = normalize_latency({"p95_ms": 800}, granularity="provider")
    degraded = degrade_endpoint({"consecutive_errors": 3}, sibling_ids=["sib"])

    assert latency.granularity == "provider"
    assert latency.endpoint_exact is False
    assert degraded.endpoint_status == "degraded"
    assert degraded.sibling_statuses == {"sib": "unchanged"}


def test_eligibility_filter_rejects_before_scoring():
    endpoint = {"matched": True, "breaker": "open", "quota": 100, "basic_probe": True, "access": "free_unlimited"}

    assert eligible_for_scoring(endpoint, required_capabilities=set()).eligible is False


@pytest.mark.spec("context-window-eligibility::Below minimum")
@pytest.mark.spec("role-scorer::Missing required capability")
@pytest.mark.parametrize(
    ("endpoint_patch", "required_capabilities", "reason"),
    [
        ({"breaker": "open"}, set(), "breaker"),
        ({"quota": 0}, set(), "quota"),
        ({"capabilities": {"text"}}, {"tools"}, "capabilities"),
    ],
)
def test_eligibility_filter_returns_distinct_edge_reasons(endpoint_patch, required_capabilities, reason):
    endpoint = {
        "access": "free_unlimited",
        "basic_probe": True,
        "quota": 100,
        "matched": True,
        "breaker": "closed",
        "capabilities": {"text", "tools"},
    }
    endpoint.update(endpoint_patch)

    decision = eligible_for_scoring(endpoint, required_capabilities=required_capabilities)

    assert decision.eligible is False
    assert decision.reason == reason


def test_aa_subscore_missing_metric_redistributes_and_all_missing_unknown():
    score = aa_subscore(
        {"intelligence_index": 50, "agentic_index": 50, "median_end_to_end_seconds": 5},
        weights={"intelligence_index": 0.4, "coding_index": 0.3, "agentic_index": 0.3},
        percentiles={"intelligence_index": (0, 100), "coding_index": (0, 100), "agentic_index": (0, 100)},
    )
    unknown = aa_subscore({}, weights={"intelligence_index": 1}, percentiles={"intelligence_index": (0, 100)})

    assert 0 < score.value < 1
    assert score.uncertainty_penalty > 0
    assert unknown.unknown is True


def test_normalize_degenerate_percentiles_is_zero():
    assert _normalize(50, 100, 100) == 0.0
    assert _normalize(50, 100, 90) == 0.0


@pytest.mark.spec("role-scorer::Price excluded")
@pytest.mark.spec("role-scorer::Unchanged inputs")
def test_latency_priority_score_excludes_price_and_hash_skips_recompute():
    assert latency_score_source(endpoint_p95=100, provider_p95=200, aa_latency=1.2) == ("endpoint", 100)
    result = score_endpoint(
        {
            "benchmark_fit": 1,
            "capability_fit": 1,
            "health": 1,
            "latency": 1,
            "quota_headroom": 1,
            "stability": 1,
            "uncertainty": 0.5,
            "price": 999,
        }
    )
    assert result.total == 5.5
    assert should_recompute_score("abc", "abc") is False


@pytest.mark.spec("role-scorer::No latency source")
def test_latency_score_source_unknown_when_every_source_missing():
    assert latency_score_source(endpoint_p95=None, provider_p95=None, aa_latency=None) == ("unknown", None)


@pytest.mark.spec("context-window-eligibility::Unknown context, no override")
@pytest.mark.spec("context-window-eligibility::Far above minimum")
def test_context_hard_filter_unknown_override_and_no_bonus():
    assert effective_context_window([128_000, 64_000, None]) == 64_000
    assert context_eligible(effective_context=32_000, minimum_context=64_000).eligible is False
    far_above = context_eligible(effective_context=1_000_000, minimum_context=64_000)
    unknown = context_eligible(effective_context=None, minimum_context=64_000)
    override = context_eligible(effective_context=None, minimum_context=64_000, manual_override=True)
    assert far_above.bonus == 0
    assert unknown.eligible is False
    assert override.eligible is True


@pytest.mark.spec("quality-gate::Below the gate")
@pytest.mark.spec("quality-gate::Missing gate metric")
@pytest.mark.spec("quality-gate::Major index change")
def test_quality_gate_hard_prefilter_unverifiable_and_index_change():
    assert evaluate_quality_gate({"agentic_index": 30}, metric="agentic_index", value=45, index_version="v1", current_version="v1").eligible is False
    missing = evaluate_quality_gate({}, metric="coding_index", value=10, index_version="v1", current_version="v1")
    changed = evaluate_quality_gate({"coding_index": 50}, metric="coding_index", value=10, index_version="v1", current_version="v2")
    assert missing.status == "unverifiable"
    assert missing.eligible is False
    assert changed.status == "needs_recalibration"
    assert changed.apply_new_plan is False
