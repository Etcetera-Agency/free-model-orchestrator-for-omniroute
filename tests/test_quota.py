from datetime import UTC, datetime, timedelta

import pytest

from fmo.access import classify_access
from fmo.omniroute import OmniRouteRequestError
from fmo.quota_attribution import (
    AttributionGroup,
    apply_group_evidence,
    attribution_capacity,
)
from fmo.quota_manager import (
    LiveQuota,
    effective_remaining,
    endpoint_binding_capacity,
    require_hard_stop,
    reset_and_reclassify,
    validate_historical_reserve,
)
from fmo.quota_research import (
    ActiveQuotaRule,
    QuotaClaim,
    activate_summary_rule,
    build_quota_query,
    research_quota_rule,
    resolve_quota_range,
    run_quota_search,
    validate_claim,
)


class SearchClient:
    def __init__(self):
        self.calls = []

    def post(self, path, payload):
        self.calls.append((path, payload))
        return {
            "answer": {"text": "Provider gives 100 requests per day with hard stop."},
            "results": [{"title": "Docs", "url": "https://provider.example/free"}],
        }


class InspectorSearchClient(SearchClient):
    def post(self, path, payload):
        self.calls.append((path, payload))
        return {
            "answer": {"text": "Provider gives between 200 and 1000 requests per day with hard stop."},
            "results": [{"title": "Docs", "url": "https://provider.example/range"}],
        }


class FallbackSearchClient:
    def __init__(self):
        self.calls = []

    def post(self, path, payload):
        self.calls.append((path, payload))
        if payload.get("provider") == "gemini-grounded-search":
            raise OmniRouteRequestError("POST", path, 429)
        return {
            "answer": None,
            "results": [
                {
                    "title": "Request for NVIDIA NIM API Rate Limit Increase (40 RPM)",
                    "url": "https://forums.developer.nvidia.com/t/rate-limit",
                    "snippet": "",
                }
            ],
        }


@pytest.mark.spec("quota-research::Quota query")
def test_research_search_uses_date_aware_query_and_persists_summary():
    client = SearchClient()
    query = build_quota_query("kilo", "kilo/free-model", today=datetime(2026, 6, 16, tzinfo=UTC))
    snapshot = run_quota_search(client, provider="kilo", model_id="kilo/free-model", query=query)

    assert "/v1/search" == client.calls[0][0]
    assert client.calls[0][1]["provider"] == "gemini-grounded-search"
    assert "2026" in client.calls[0][1]["query"]
    assert "requests/day" in client.calls[0][1]["query"]
    assert "tokens/month" in client.calls[0][1]["query"]
    assert "source URLs" in client.calls[0][1]["query"]
    assert len(client.calls[0][1]["query"]) <= 500
    assert snapshot.answer_text == "Provider gives 100 requests per day with hard stop."
    assert snapshot.content_hash


@pytest.mark.spec("quota-research::Search fallback when primary provider is rate-limited")
def test_research_search_falls_back_to_default_provider_and_uses_result_text():
    search_client = FallbackSearchClient()
    query = build_quota_query("nvidia", "*", today=datetime(2026, 6, 16, tzinfo=UTC))
    snapshot = run_quota_search(search_client, provider="nvidia", model_id="*", query=query)

    assert search_client.calls[0][1]["provider"] == "gemini-grounded-search"
    assert "provider" not in search_client.calls[1][1]
    assert "40 RPM" in snapshot.answer_text

    result = research_quota_rule(
        FallbackSearchClient(),
        provider="nvidia",
        model_id="*",
        today=datetime(2026, 6, 16, tzinfo=UTC),
        summary_confidence_cap=0.7,
    )

    assert result.rule is not None
    assert result.rule.claim.metric == "requests"
    assert result.rule.claim.amount == 40
    assert result.rule.claim.window == "minute"


@pytest.mark.spec("quota-research::Quota query")
def test_research_search_query_omits_internal_provider_ids_to_stay_under_live_limit():
    query = build_quota_query(
        "openai-compatible-chat-95c7538c-1c44-4196-baa0-d06888eefe19",
        "aihubmix/coding-glm-4.6-free",
        today=datetime(2026, 6, 16, tzinfo=UTC),
    )

    assert "openai-compatible-chat-95c7538c-1c44-4196-baa0-d06888eefe19" not in query
    assert "aihubmix/coding-glm-4.6-free" in query
    assert len(query) <= 500


@pytest.mark.spec("quota-research::Quota query")
def test_provider_account_quota_query_uses_topology_scope_without_representative_model():
    query = build_quota_query("antigravity", "*", today=datetime(2026, 6, 16, tzinfo=UTC))

    assert "quota topology" in query
    assert "provider antigravity" in query
    assert "model-group/per-model" in query
    assert "requests/minute" in query
    assert "model antigravity/" not in query
    assert len(query) <= 500


@pytest.mark.spec("quota-research::Prior limit inside the range is kept")
def test_quota_range_keeps_prior_limit_inside_range():
    assert resolve_quota_range(200, 1000, previous_limit=600) == 600


@pytest.mark.spec("quota-research::Range below the prior limit resolves to its upper bound")
def test_quota_range_below_prior_uses_upper_bound():
    assert resolve_quota_range(200, 1000, previous_limit=1200) == 1000


@pytest.mark.spec("quota-research::Range above the prior limit resolves to its lower bound")
def test_quota_range_above_prior_uses_lower_bound():
    assert resolve_quota_range(200, 1000, previous_limit=100) == 200


@pytest.mark.spec("quota-research::No prior limit resolves conservatively")
def test_quota_range_without_prior_uses_lower_bound():
    assert resolve_quota_range(200, 1000, previous_limit=None) == 200


@pytest.mark.spec("quota-research::Prior limit reaches the inspector prompt")
def test_previous_limit_reaches_quota_inspector_prompt():
    prompts = []

    class Inspector:
        def complete(self, *, site, context, response_model):
            assert site.model is None
            prompt_template = site.prompt_path.read_text(encoding="utf-8")
            prompts.append(prompt_template.replace("{{previous_limit}}", context["previous_limit"]))
            return response_model(
                metric="requests",
                amount=200,
                window="day",
                evidence=["https://provider.example/range"],
                hard_stop=True,
            )

    result = research_quota_rule(
        InspectorSearchClient(),
        provider="kilo",
        model_id="kilo/free-model",
        today=datetime(2026, 6, 16, tzinfo=UTC),
        summary_confidence_cap=0.70,
        instructor_call=Inspector(),
        previous_limit=600,
    )

    assert result.rule is not None
    assert result.rule.safe_mode is True
    assert "600" in prompts[0]
    assert "closest to" in prompts[0]


@pytest.mark.spec("quota-research::Invalid extracted claim")
def test_quota_claim_validation_rejects_bad_amount_window_and_missing_evidence():
    valid = QuotaClaim(metric="requests", amount=100, window="day", evidence=["docs"], hard_stop=True)
    assert validate_claim(valid).amount == 100

    with pytest.raises(ValueError):
        validate_claim(QuotaClaim(metric="requests", amount=0, window="day", evidence=["docs"], hard_stop=True))
    with pytest.raises(ValueError):
        validate_claim(QuotaClaim(metric="requests", amount=10, window="fortnight", evidence=["docs"], hard_stop=True))
    with pytest.raises(ValueError):
        validate_claim(QuotaClaim(metric="requests", amount=10, window="day", evidence=[], hard_stop=True))


@pytest.mark.spec("quota-research::Summary worsens quota")
def test_summary_activation_caps_confidence_and_worsened_quota_safe_mode():
    active = activate_summary_rule(
        QuotaClaim(metric="requests", amount=100, window="day", evidence=["summary"], hard_stop=True),
        summary_confidence_cap=0.70,
        previous_limit=200,
    )

    assert active.confidence == 0.70
    assert active.activated_by == "summary"
    assert active.capacity_class == "opportunistic"
    assert active.safe_mode is True


def _quota_rule(claim: QuotaClaim, axes: tuple[QuotaClaim, ...] = ()) -> ActiveQuotaRule:
    return ActiveQuotaRule(
        claim=claim,
        confidence=1.0,
        activated_by="test",
        capacity_class="confirmed",
        safe_mode=False,
        axes=axes or (claim,),
    )


@pytest.mark.spec("quota-manager::Tightest axis binds the capacity")
@pytest.mark.spec("quota-manager::Live quota requests do not contribute to the daily budget")
def test_endpoint_binding_capacity_uses_research_axis_not_live_request_rate():
    research = _quota_rule(QuotaClaim("requests", 100, "day", ["research"], True))
    live = LiveQuota(
        "provider",
        "connection",
        limit=None,
        remaining=None,
        reset_at=datetime.now(UTC),
        learned_request_limit=10_000,
        learned_request_remaining=10_000,
    )

    capacity = endpoint_binding_capacity(
        research_rule=research,
        live_quota=live,
        tokens_per_request=2000,
    )

    assert capacity == 100


@pytest.mark.spec("quota-manager::Calibrated endpoint contributes its axis")
def test_endpoint_binding_capacity_includes_calibrated_token_axis():
    research = _quota_rule(QuotaClaim("requests", 50, "day", ["research"], True))
    calibrated = _quota_rule(QuotaClaim("tokens", 1000, "day", ["calibration"], True))

    capacity = endpoint_binding_capacity(
        research_rule=research,
        calibration_rule=calibrated,
        tokens_per_request=100,
    )

    assert capacity == 10


@pytest.mark.spec("quota-manager::Sub-day request axis excluded")
def test_endpoint_binding_capacity_excludes_sub_day_request_axis():
    research = _quota_rule(
        QuotaClaim("requests", 15, "minute", ["research"], True),
        axes=(
            QuotaClaim("requests", 15, "minute", ["research"], True),
            QuotaClaim("requests", 800, "day", ["research"], True),
        ),
    )

    assert endpoint_binding_capacity(research_rule=research) == 800


@pytest.mark.spec("access-classifier::Live API overrides models.dev")
def test_access_classifier_order_trust_and_free_quota_preconditions():
    assert classify_access({"disabled": True}).status == "unavailable"
    assert classify_access({"price_input": 0, "price_output": 0}).status == "free_unlimited"
    assert classify_access({"models_dev_free": True, "live_paid_charge": True}).status == "paid_only_excluded"
    assert (
        classify_access({"quota_rule": True, "limit": 100, "remaining": 50, "hard_stop": True}).status
        == "unknown_excluded"
    )
    available = classify_access(
        {"quota_rule": True, "limit": 100, "remaining": 50, "reset_at": datetime.now(UTC), "hard_stop": True}
    )
    assert available.status == "free_quota_available"


@pytest.mark.spec("access-classifier::Exhausted by safety buffer")
def test_access_classifier_quota_exhausted_at_safety_buffer_boundary():
    decision = classify_access(
        {
            "quota_rule": True,
            "limit": 100,
            "remaining": 10,
            "reset_at": datetime.now(UTC),
            "hard_stop": True,
            "safety_buffer": 10,
        }
    )

    assert decision.status == "free_quota_exhausted"
    assert decision.reason_code == "safety_buffer_exhausted"


@pytest.mark.spec("access-classifier::Missing quota precondition")
@pytest.mark.parametrize(
    "missing",
    [
        {"hard_stop": False},
        {"limit": None},
        {"remaining": None},
        {"reset_at": None},
    ],
)
def test_access_classifier_quota_rule_missing_precondition(missing):
    evidence = {
        "quota_rule": True,
        "limit": 100,
        "remaining": 50,
        "reset_at": datetime.now(UTC),
        "hard_stop": True,
    }
    evidence.update(missing)

    decision = classify_access(evidence)

    assert decision.status == "unknown_excluded"
    assert decision.reason_code == "missing_quota_precondition"


@pytest.mark.spec("access-classifier::Promotion expired")
def test_access_classifier_promotion_expired():
    decision = classify_access({"promotion_expired": True})

    assert decision.status == "free_promotional_expired"
    assert decision.reason_code == "promotion_expired"


@pytest.mark.spec("access-classifier::Empty evidence")
def test_access_classifier_empty_evidence_fails_closed():
    decision = classify_access({})

    assert decision.status == "unknown_excluded"
    assert decision.reason_code == "fail_closed"


@pytest.mark.spec("access-classifier::Removed beats zero price")
@pytest.mark.parametrize("unavailable_flag", ["removed", "permanently_broken"])
def test_access_classifier_unavailable_beats_zero_price(unavailable_flag):
    decision = classify_access({unavailable_flag: True, "price_input": 0, "price_output": 0})

    assert decision.status == "unavailable"
    assert decision.reason_code == "endpoint_unavailable"


@pytest.mark.spec("access-classifier::Manual deny beats zero price")
def test_access_classifier_manual_deny_beats_zero_price():
    decision = classify_access({"manual_deny": True, "price_input": 0, "price_output": 0})

    assert decision.status == "paid_only_excluded"
    assert decision.reason_code == "trusted_paid_evidence"


@pytest.mark.spec("quota-attribution::No OmniRoute pool")
@pytest.mark.spec("quota-attribution::Two accounts, independence unknown")
@pytest.mark.spec("quota-attribution::Confirmed independence")
@pytest.mark.spec("quota-attribution::IP-scoped no-auth provider")
def test_attribution_capacity_status_and_merge_split_evidence():
    groups = [
        AttributionGroup("a", "confirmed", 100),
        AttributionGroup("b", "inferred", 100),
        AttributionGroup("c", "assumed_shared", 100),
        AttributionGroup("d", "assumed_shared", 100),
        AttributionGroup("e", "unknown", 100),
    ]

    assert attribution_capacity(groups).guaranteed == 200
    assert attribution_capacity(groups).opportunistic == 50
    merged = apply_group_evidence(groups[:2], evidence={"shared_counter": True})
    split = apply_group_evidence(groups[:2], evidence={"confirmed_independence": True})
    assert len(merged) == 1
    assert all(group.status == "confirmed" for group in split)
    assert all(group.recalculate_allocation for group in split)


@pytest.mark.spec("quota-manager::Production request")
@pytest.mark.spec("quota-manager::After reset")
@pytest.mark.spec("quota-manager::Missing reserve")
def test_effective_remaining_hard_stop_reset_and_historical_reserve():
    assert (
        effective_remaining(limit=100, provider_remaining=60, local_used=30, pending_reserved=10, safety_buffer=5) == 45
    )
    assert (
        effective_remaining(limit=None, provider_remaining=None, local_used=None, pending_reserved=0, safety_buffer=0)
        is None
    )

    with pytest.raises(ValueError):
        require_hard_stop(False)
    with pytest.raises(ValueError):
        validate_historical_reserve({"source": "historical", "reserve_applied": False})

    calls = []

    def fetch_live():
        calls.append("fetch")
        return {"limit": 100, "remaining": 100, "reset_at": datetime.now(UTC) + timedelta(days=1)}

    def reclassify(payload):
        calls.append("classify")
        return payload

    reset_and_reclassify(fetch_live, reclassify)
    assert calls == ["fetch", "classify"]


@pytest.mark.spec("quota-manager::No reliable counter")
def test_effective_remaining_all_sources_unknown_is_none():
    assert (
        effective_remaining(limit=None, provider_remaining=None, local_used=None, pending_reserved=5, safety_buffer=5)
        is None
    )


@pytest.mark.spec("quota-manager::Negative effective remaining")
def test_effective_remaining_preserves_negative_after_reservations_and_buffer():
    assert (
        effective_remaining(limit=100, provider_remaining=3, local_used=99, pending_reserved=4, safety_buffer=2) == -5
    )


@pytest.mark.spec("quota-manager::Remaining expressed in request-equivalents per day")
def test_effective_remaining_uses_converted_request_equivalent_values():
    assert (
        effective_remaining(limit=10, provider_remaining=7.5, local_used=2, pending_reserved=1, safety_buffer=0.5) == 6
    )


@pytest.mark.spec("quota-manager::No hard stop")
@pytest.mark.spec("quota-manager::Hard stop false")
def test_require_hard_stop_false_raises_value_error():
    with pytest.raises(ValueError, match="hard stop required"):
        require_hard_stop(False)
