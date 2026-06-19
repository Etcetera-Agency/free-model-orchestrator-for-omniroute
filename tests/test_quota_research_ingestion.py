from datetime import datetime, timezone
from urllib.parse import urlsplit

import pytest

from fmo.omniroute import OmniRouteClient
from fmo.quota_research import QuotaResearchError, research_quota_rule

from _fixtures import fixture_body
import pytest


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
