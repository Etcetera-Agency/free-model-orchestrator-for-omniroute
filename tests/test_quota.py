from datetime import datetime, timedelta, timezone

import pytest

from fmo.access import classify_access
from fmo.quota_attribution import (
    AttributionGroup,
    apply_group_evidence,
    attribution_capacity,
)
from fmo.quota_manager import (
    effective_remaining,
    require_hard_stop,
    reset_and_reclassify,
    validate_historical_reserve,
)
from fmo.quota_research import (
    QuotaClaim,
    activate_summary_rule,
    build_quota_query,
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


def test_research_search_uses_date_aware_query_and_persists_summary():
    client = SearchClient()
    query = build_quota_query("kilo", "kilo/free-model", today=datetime(2026, 6, 16, tzinfo=timezone.utc))
    snapshot = run_quota_search(client, provider="kilo", model_id="kilo/free-model", query=query)

    assert "/v1/search" == client.calls[0][0]
    assert client.calls[0][1]["provider"] == "gemini-grounded-search"
    assert "2026" in client.calls[0][1]["query"]
    assert snapshot.answer_text == "Provider gives 100 requests per day with hard stop."
    assert snapshot.content_hash


def test_quota_claim_validation_rejects_bad_amount_window_and_missing_evidence():
    valid = QuotaClaim(metric="requests", amount=100, window="day", evidence=["docs"], hard_stop=True)
    assert validate_claim(valid).amount == 100

    with pytest.raises(ValueError):
        validate_claim(QuotaClaim(metric="requests", amount=0, window="day", evidence=["docs"], hard_stop=True))
    with pytest.raises(ValueError):
        validate_claim(QuotaClaim(metric="requests", amount=10, window="fortnight", evidence=["docs"], hard_stop=True))
    with pytest.raises(ValueError):
        validate_claim(QuotaClaim(metric="requests", amount=10, window="day", evidence=[], hard_stop=True))


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


def test_access_classifier_order_trust_and_free_quota_preconditions():
    assert classify_access({"disabled": True}).status == "unavailable"
    assert classify_access({"price_input": 0, "price_output": 0}).status == "free_unlimited"
    assert classify_access({"models_dev_free": True, "live_paid_charge": True}).status == "paid_only_excluded"
    assert classify_access({"quota_rule": True, "limit": 100, "remaining": 50, "hard_stop": True}).status == "unknown_excluded"
    available = classify_access(
        {"quota_rule": True, "limit": 100, "remaining": 50, "reset_at": datetime.now(timezone.utc), "hard_stop": True}
    )
    assert available.status == "free_quota_available"


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


def test_effective_remaining_hard_stop_reset_and_historical_reserve():
    assert effective_remaining(limit=100, provider_remaining=60, local_used=30, pending_reserved=10, safety_buffer=5) == 45
    assert effective_remaining(limit=None, provider_remaining=None, local_used=None, pending_reserved=0, safety_buffer=0) is None

    with pytest.raises(ValueError):
        require_hard_stop(False)
    with pytest.raises(ValueError):
        validate_historical_reserve({"source": "historical", "reserve_applied": False})

    calls = []

    def fetch_live():
        calls.append("fetch")
        return {"limit": 100, "remaining": 100, "reset_at": datetime.now(timezone.utc) + timedelta(days=1)}

    def reclassify(payload):
        calls.append("classify")
        return payload

    reset_and_reclassify(fetch_live, reclassify)
    assert calls == ["fetch", "classify"]
