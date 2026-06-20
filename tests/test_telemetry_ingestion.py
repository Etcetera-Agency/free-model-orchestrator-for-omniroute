from urllib.parse import urlsplit

import pytest

from fmo.omniroute import OmniRouteClient
from fmo.telemetry import sync_live_telemetry

from _fixtures import fixture_body
import pytest


class _FixtureResponse:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self.headers = {}
        self._body = body

    def json(self):
        return self._body


class _TelemetryTransport:
    def __init__(self, *, status_code=200, analytics_body=None):
        self.status_code = status_code
        self.analytics_body = (
            analytics_body if analytics_body is not None else fixture_body("omniroute_api_usage_analytics")
        )
        self.requested_paths = []

    def request(self, method, url, headers=None, json=None, timeout=None):
        path = urlsplit(url).path
        self.requested_paths.append(path)
        if path == "/api/usage/analytics":
            return _FixtureResponse(self.status_code, self.analytics_body)
        raise AssertionError(f"unexpected telemetry request: {path}")


@pytest.mark.spec("telemetry-sync::Telemetry fetched before normalization")
def test_live_telemetry_fetches_usage_analytics_and_normalizes_real_shapes():
    transport = _TelemetryTransport()
    client = OmniRouteClient(base_url="https://omniroute.test", api_key="manage-key", transport=transport)

    snapshot = sync_live_telemetry(client)

    assert transport.requested_paths == ["/api/usage/analytics"]
    assert snapshot.errors == []
    longcat = snapshot.provider_metrics["longcat"]
    assert longcat.requests == 6
    assert longcat.avg_latency_ms == 1810
    assert longcat.latency_granularity == "provider"
    assert longcat.p95_ms is None
    assert longcat.failure_count == 6
    assert snapshot.model_metrics[("longcat", "longcat-2.0-preview")].requests == 2


@pytest.mark.spec("telemetry-sync::Telemetry source unavailable")
def test_live_telemetry_unavailable_source_leaves_metrics_unknown():
    transport = _TelemetryTransport(
        status_code=500,
        analytics_body=fixture_body("omniroute_api_usage_analytics_http_500"),
    )
    client = OmniRouteClient(base_url="https://omniroute.test", api_key="manage-key", transport=transport)

    snapshot = sync_live_telemetry(client)

    assert snapshot.provider_metrics == {}
    assert snapshot.model_metrics == {}
    assert snapshot.errors[0].reason == "http_error"
