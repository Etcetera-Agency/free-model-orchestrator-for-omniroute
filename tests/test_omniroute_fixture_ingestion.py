"""Ingest recorded OmniRoute management responses through the real parsers.

These replace hand-built OmniRoute payloads: every body comes from
``reference/fixtures/external-responses`` captured from a running instance, and
is driven through ``OmniRouteClient`` and the registry/scanner/account parsers
so the real management shapes are exercised end to end.
"""

from urllib.parse import urlsplit

import pytest

from _fixtures import fixture_body, load_fixture
from fmo.accounts import group_quota_pools, usable_capacity
from fmo.omniroute import OmniRouteClient
from fmo.registry import sync_free_registry

# OmniRoute management path -> recorded fixture name.
PATH_FIXTURES = {
    "/api/combos": "omniroute_api_combos",
    "/api/providers": "omniroute_api_providers",
    "/api/free-models": "omniroute_api_free_models",
    "/api/free-provider-rankings": "omniroute_api_free_provider_rankings",
    "/api/free-tier/summary": "omniroute_api_free_tier_summary",
    "/api/rate-limits": "omniroute_api_rate_limits",
    "/v1/models": "omniroute_v1_models",
}


class _FixtureResponse:
    def __init__(self, body):
        self.status_code = 200
        self.headers = {}
        self._body = body

    def json(self):
        return self._body


class _FixtureTransport:
    """Replays recorded bodies keyed by the requested management path."""

    def __init__(self):
        self.requested_paths = []

    def request(self, method, url, headers=None, json=None, timeout=None):
        path = urlsplit(url).path
        self.requested_paths.append(path)
        fixture = PATH_FIXTURES[path]
        return _FixtureResponse(fixture_body(fixture))


@pytest.fixture()
def client():
    return OmniRouteClient(base_url="https://omniroute.test", api_key="manage-key", transport=_FixtureTransport())


@pytest.mark.spec("free-provider-registry-sync::Registry fetched before build")
def test_free_models_fixture_builds_registry(client):
    payload = client.get("/api/free-models")

    registry = sync_free_registry(payload)

    assert ("gemini", "gemini-2.0-flash") in registry.models
    gemini = registry.models[("gemini", "gemini-2.0-flash")]
    assert gemini.display_name == "Gemini 2.0 Flash"
    assert gemini.free_type == "recurring-daily"
    # `poolKey` is null in the recording, so it falls back to provider:model.
    assert gemini.pool_key == "gemini:gemini-2.0-flash"
    assert registry.pool_budgets["gemini:gemini-2.0-flash"] == 25000000


@pytest.mark.spec("account-discovery::Rate limits unavailable")
def test_providers_fixture_groups_quota_pools_conservatively(client):
    connections = client.get("/api/providers")["connections"]

    pools = group_quota_pools(connections)

    # Recorded connections carry no confirmed independence/quota, so they must
    # not contribute usable capacity.
    assert usable_capacity(pools) == 0.0
    windsurf = [c for c in connections if c["provider"] == "windsurf"]
    assert windsurf, "fixture should contain a windsurf connection"
    pool = pools[str(windsurf[0]["id"])]
    assert pool.independence_status == "assumed_shared"


@pytest.mark.spec("account-discovery::Rate-limit fetch unavailable")
def test_rate_limits_and_rankings_fixtures_have_expected_shape(client):
    rate_limits = client.get("/api/rate-limits")
    rankings = client.get("/api/free-provider-rankings")

    assert isinstance(rate_limits["connections"], list)
    assert all("connectionId" in c and "provider" in c for c in rate_limits["connections"])

    ranking = rankings["rankings"][0]
    assert {"id", "name", "topModel", "averageScore"} <= set(ranking)
    assert "modelId" in ranking["topModel"]


@pytest.mark.spec("combo-applier::Non-existent combo is not created")
@pytest.mark.spec("omniroute-client::Bridge exposes management combo routes")
def test_live_combos_fixture_records_seeded_operator_state(client):
    recording = load_fixture("omniroute_api_combos")
    payload = client.get("/api/combos")

    assert recording["status"] == 200
    assert recording["path"] == "/api/combos"
    assert recording["headers"]["x-omniroute-route-class"] == "MANAGEMENT"
    combos = {combo["name"]: combo for combo in payload["combos"]}
    assert set(combos) == {
        "fmo-chat-combo",
        "fmo-research-combo",
        "fmo-coding-combo",
        "fmo-title-generation",
        "fmo-vision",
        "fmo-compression",
        "fmo-approval",
        "fmo-skills",
        "fmo-mcp",
        "fmo-triage-specifier",
        "fmo-kanban-decomposer",
        "fmo-profile-describer",
        "fmo-curator",
    }
    assert all(combo["models"][0]["model"] == "oc/big-pickle" for combo in combos.values())


@pytest.mark.spec("omniroute-client::Module needs OmniRoute data")
def test_client_requests_management_paths(client):
    client.get("/api/free-models")

    assert client.transport.requested_paths == ["/api/free-models"]
