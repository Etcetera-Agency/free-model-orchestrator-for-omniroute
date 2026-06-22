from datetime import datetime, timezone
from urllib.parse import urlsplit

import pytest

from fmo.omniroute import OmniRouteClient
from fmo.quota_research import (
    ActiveQuotaRule,
    NoAuthCalibrationEvidence,
    QuotaClaim,
    QuotaResearchError,
    SearchSnapshot,
    extract_summary_claim,
    extract_summary_claims,
    promote_noauth_calibration,
    research_quota_rule,
    resolve_noauth_quota,
)

from _fixtures import fixture_body


class _FixtureResponse:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self.headers = {}
        self._body = body

    def json(self):
        return self._body


class _SearchTransport:
    def __init__(self, *, status_code=200, body=None):
        self.status_code = status_code
        self.body = body if body is not None else fixture_body("omniroute_v1_search_quota_gemini_grounded")
        self.requests = []

    def request(self, method, url, headers=None, json=None, timeout=None):
        path = urlsplit(url).path
        self.requests.append({"method": method, "path": path, "headers": headers or {}, "json": json})
        if path == "/v1/search":
            return _FixtureResponse(self.status_code, self.body)
        raise AssertionError(f"unexpected search request: {path}")


def _snapshot(answer_text: str) -> SearchSnapshot:
    return SearchSnapshot(
        query="quota query",
        answer_text=answer_text,
        evidence_urls=("https://provider.example/free-quota",),
        content_hash="hash",
    )


def _axis_tuples(claims):
    return [(claim.metric, claim.amount, claim.window) for claim in claims]


@pytest.mark.spec("quota-research::Live search performed")
@pytest.mark.spec("quota-research::Endpoint absent from OmniRoute registry")
def test_live_quota_research_calls_omniroute_search_and_extracts_summary_rule():
    transport = _SearchTransport()
    client = OmniRouteClient(base_url="https://omniroute.test", api_key="search-key", transport=transport)

    result = research_quota_rule(
        client,
        provider="kilo",
        model_id="kilo/free-model",
        today=datetime(2026, 6, 18, tzinfo=timezone.utc),
        summary_confidence_cap=0.7,
    )

    request = transport.requests[0]
    assert request["method"] == "POST"
    assert request["path"] == "/v1/search"
    assert request["headers"]["Authorization"] == "Bearer search-key"
    assert request["json"]["provider"] == "gemini-grounded-search"
    assert result.snapshot.content_hash
    assert result.rule is not None
    assert result.rule.claim.amount == 100
    assert result.rule.claim.window == "day"
    assert result.rule.activated_by == "summary"


@pytest.mark.spec("quota-research::Token budget summary")
def test_summary_token_budget_extracts_token_month_axis():
    claim = extract_summary_claim(_snapshot("Free tier has 1,000,000 tokens per month with hard stop."))

    assert claim.metric == "tokens"
    assert claim.amount == 1_000_000
    assert claim.window == "month"


@pytest.mark.spec("quota-research::Request limit summary unchanged")
def test_summary_request_budget_still_extracts_request_day_axis():
    claim = extract_summary_claim(_snapshot("Free tier has 100 requests per day with hard stop."))

    assert claim.metric == "requests"
    assert claim.amount == 100
    assert claim.window == "day"


@pytest.mark.spec("quota-research::Both axes present")
def test_summary_extracts_request_and_token_axes_when_both_present():
    claims = extract_summary_claims(
        _snapshot("Free tier has 100 requests per day and 1,000,000 tokens per month with hard stop.")
    )

    assert _axis_tuples(claims) == [
        ("requests", 100, "day"),
        ("tokens", 1_000_000, "month"),
    ]


@pytest.mark.spec("quota-research::Requests-per-minute only does not activate")
def test_summary_request_rate_only_does_not_activate_capacity_rule():
    transport = _SearchTransport(
        body={
            "answer": {"text": "Free tier allows 10 requests per minute with hard stop."},
            "results": [{"url": "https://provider.example/free-quota"}],
        }
    )
    client = OmniRouteClient(base_url="https://omniroute.test", api_key="search-key", transport=transport)

    result = research_quota_rule(
        client,
        provider="kilo",
        model_id="kilo/free-model",
        today=datetime(2026, 6, 18, tzinfo=timezone.utc),
        summary_confidence_cap=0.7,
    )

    assert result.rule is None
    assert result.error is not None
    assert result.error.reason == "missing_capacity_axis"


@pytest.mark.spec("quota-research::Inspector token claim carried through")
def test_inspector_token_claim_is_carried_through_to_active_rule():
    transport = _SearchTransport()
    client = OmniRouteClient(base_url="https://omniroute.test", api_key="search-key", transport=transport)

    result = research_quota_rule(
        client,
        provider="kilo",
        model_id="kilo/free-model",
        today=datetime(2026, 6, 18, tzinfo=timezone.utc),
        summary_confidence_cap=0.7,
        instructor_call=lambda _payload: {
            "metric": "tokens",
            "amount": 1_000_000,
            "window": "month",
            "evidence": ["inspector fixture"],
            "hard_stop": True,
        },
    )

    assert result.rule is not None
    assert result.rule.claim.metric == "tokens"
    assert result.rule.claim.amount == 1_000_000
    assert result.rule.claim.window == "month"
    assert result.rule.confidence == 0.7
    assert _axis_tuples(result.rule.axes) == [("tokens", 1_000_000, "month")]


@pytest.mark.spec("quota-research::Inspector sub-day request claim routed out")
def test_inspector_request_rate_claim_does_not_activate_capacity_rule():
    transport = _SearchTransport()
    client = OmniRouteClient(base_url="https://omniroute.test", api_key="search-key", transport=transport)

    result = research_quota_rule(
        client,
        provider="kilo",
        model_id="kilo/free-model",
        today=datetime(2026, 6, 18, tzinfo=timezone.utc),
        summary_confidence_cap=0.7,
        instructor_call=lambda _payload: {
            "metric": "requests",
            "amount": 10,
            "window": "minute",
            "evidence": ["inspector fixture"],
            "hard_stop": True,
        },
    )

    assert result.rule is None
    assert result.error is not None
    assert result.error.reason == "reactive_rate_gate"


@pytest.mark.spec("quota-research::Search unavailable")
def test_live_quota_research_unavailable_source_produces_no_rule():
    transport = _SearchTransport(
        status_code=500,
        body=fixture_body("omniroute_v1_search_http_500"),
    )
    client = OmniRouteClient(base_url="https://omniroute.test", api_key="search-key", transport=transport)

    result = research_quota_rule(
        client,
        provider="kilo",
        model_id="kilo/free-model",
        today=datetime(2026, 6, 18, tzinfo=timezone.utc),
        summary_confidence_cap=0.7,
    )

    assert isinstance(result.error, QuotaResearchError)
    assert result.error.reason == "http_error"
    assert result.rule is None


def _active_rule(amount=50_000, window="day"):
    return ActiveQuotaRule(
        claim=QuotaClaim(
            metric="tokens",
            amount=amount,
            window=window,
            evidence=["https://omniroute.test/usage/opencode-zen"],
            hard_stop=True,
        ),
        confidence=1.0,
        activated_by="live_quota",
        capacity_class="confirmed",
        safe_mode=False,
    )


@pytest.mark.spec("quota-research::Opencode shares opencode-zen quota")
def test_opencode_noauth_alias_uses_opencode_zen_quota_and_models():
    sibling_rule = _active_rule()

    result = resolve_noauth_quota(
        provider="opencode",
        model_id="qwen/qwen3-coder",
        quota_rules={("opencode-zen", "qwen/qwen3-coder"): sibling_rule},
        provider_models={"opencode-zen": ("qwen/qwen3-coder", "z-ai/glm-4.5")},
    )

    assert result.status == "shared_capacity"
    assert result.usable is True
    assert result.rule is sibling_rule
    assert result.quota_source_provider == "opencode-zen"
    assert result.model_source_provider == "opencode-zen"
    assert result.shared_with == "opencode-zen"
    assert result.model_ids == ("qwen/qwen3-coder", "z-ai/glm-4.5")
    assert result.independence_status == "assumed_shared"
    assert result.counted_as_independent is False


@pytest.mark.spec("quota-research::Alias quota source missing")
def test_noauth_alias_without_sibling_quota_stays_unusable():
    result = resolve_noauth_quota(
        provider="opencode",
        model_id="qwen/qwen3-coder",
        quota_rules={},
        provider_models={"opencode-zen": ("qwen/qwen3-coder",)},
    )

    assert result.status == "alias_quota_missing"
    assert result.usable is False
    assert result.rule is None
    assert result.shared_with is None
    assert result.counted_as_independent is False


@pytest.mark.spec("quota-research::Unknown no-auth quota requires observation")
def test_unknown_noauth_quota_requires_operator_observation_before_use():
    result = resolve_noauth_quota(
        provider="anonymous-labs",
        model_id="anonymous/model",
        quota_rules={},
        provider_models={},
    )

    assert result.status == "calibration_required"
    assert result.usable is False
    assert result.rule is None
    assert result.action == "place_first_in_combo_and_observe_omniroute_token_usage"


@pytest.mark.spec("quota-research::Calibrated usage promotes quota")
def test_complete_noauth_calibration_promotes_observed_quota_rule():
    result = promote_noauth_calibration(
        provider="anonymous-labs",
        model_id="anonymous/model",
        evidence=NoAuthCalibrationEvidence(
            observed_tokens=48_000,
            inferred_limit=50_000,
            reset_window="day",
            hard_stop=True,
            evidence=("omniroute usage 2026-06-21 run abc123",),
        ),
    )

    assert result.status == "active"
    assert result.usable is True
    assert result.rule is not None
    assert result.rule.claim.metric == "tokens"
    assert result.rule.claim.amount == 50_000
    assert result.rule.claim.window == "day"
    assert result.rule.claim.hard_stop is True
    assert result.rule.activated_by == "operator_observed_omniroute_usage"
    assert result.rule.capacity_class == "calibrated"


@pytest.mark.spec("quota-research::Incomplete calibration stays inactive")
def test_incomplete_noauth_calibration_does_not_activate_quota():
    result = promote_noauth_calibration(
        provider="anonymous-labs",
        model_id="anonymous/model",
        evidence=NoAuthCalibrationEvidence(
            observed_tokens=48_000,
            inferred_limit=50_000,
            evidence=("omniroute usage 2026-06-21 run abc123",),
        ),
    )

    assert result.status == "calibration_required"
    assert result.usable is False
    assert result.rule is None
