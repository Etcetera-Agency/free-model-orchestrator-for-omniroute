from copy import deepcopy
from urllib.parse import urlsplit

from fmo.accounts import discover_live_accounts, usable_capacity
from fmo.omniroute import OmniRouteClient

from _fixtures import fixture_body


class _FixtureResponse:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self.headers = {}
        self._body = body

    def json(self):
        return self._body


class _AccountTransport:
    def __init__(self, *, providers_body=None, rate_limits_status=200, rate_limits_body=None):
        self.providers_body = providers_body if providers_body is not None else fixture_body("omniroute_api_providers")
        self.rate_limits_status = rate_limits_status
        self.rate_limits_body = (
            rate_limits_body if rate_limits_body is not None else fixture_body("omniroute_api_rate_limits")
        )
        self.requested_paths = []

    def request(self, method, url, headers=None, json=None, timeout=None):
        path = urlsplit(url).path
        self.requested_paths.append(path)
        if path == "/api/providers":
            return _FixtureResponse(200, self.providers_body)
        if path == "/api/rate-limits":
            return _FixtureResponse(self.rate_limits_status, self.rate_limits_body)
        raise AssertionError(f"unexpected account request: {path}")


def test_live_account_discovery_fetches_connections_and_rate_limits_before_grouping():
    transport = _AccountTransport()
    client = OmniRouteClient(base_url="https://omniroute.test", api_key="manage-key", transport=transport)

    outcome = discover_live_accounts(client)

    assert transport.requested_paths == ["/api/providers", "/api/rate-limits"]
    assert outcome.rate_limits_available is True
    assert len(outcome.connections) == len(fixture_body("omniroute_api_providers")["connections"])
    assert usable_capacity(outcome.pools) == 0.0
    windsurf = next(connection for connection in outcome.connections if connection["provider"] == "windsurf")
    assert windsurf["rate_limit"]["enabled"] is False


def test_live_account_discovery_rate_limit_failure_is_conservative():
    providers_body = deepcopy(fixture_body("omniroute_api_providers"))
    providers_body["connections"][0].update(
        {
            "upstream_account_id": "acct-confirmed",
            "quota": 100,
            "status": "confirmed",
        }
    )
    transport = _AccountTransport(
        providers_body=providers_body,
        rate_limits_status=500,
        rate_limits_body=fixture_body("omniroute_api_rate_limits_http_500"),
    )
    client = OmniRouteClient(base_url="https://omniroute.test", api_key="manage-key", transport=transport)

    outcome = discover_live_accounts(client)

    assert outcome.rate_limits_available is False
    assert all(connection["status"] != "confirmed" for connection in outcome.connections)
    assert usable_capacity(outcome.pools) == 0.0
