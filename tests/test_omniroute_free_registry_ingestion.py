from copy import deepcopy
from pathlib import Path
from urllib.parse import urlsplit

import psycopg

from fmo.db import MigrationRunner
from fmo.omniroute import OmniRouteClient
from fmo.registry import persist_free_registry_outcome, sync_live_free_registry, validate_free_registry_payload

from _fixtures import fixture_body


class _FixtureResponse:
    def __init__(self, body):
        self.status_code = 200
        self.headers = {}
        self._body = body

    def json(self):
        return self._body


class _RegistryTransport:
    def __init__(self):
        self.requested_paths = []

    def request(self, method, url, headers=None, json=None, timeout=None):
        path = urlsplit(url).path
        self.requested_paths.append(path)
        if path == "/api/free-models":
            return _FixtureResponse(fixture_body("omniroute_api_free_models"))
        if path == "/api/free-provider-rankings":
            return _FixtureResponse(fixture_body("omniroute_api_free_provider_rankings"))
        raise AssertionError(f"unexpected free-registry request: {path}")


def test_live_free_registry_fetches_omniroute_fixtures_before_build():
    transport = _RegistryTransport()
    client = OmniRouteClient(base_url="https://omniroute.test", api_key="manage-key", transport=transport)

    outcome = sync_live_free_registry(client)

    assert transport.requested_paths == ["/api/free-models", "/api/free-provider-rankings"]
    assert outcome.model_count == len(fixture_body("omniroute_api_free_models")["models"])
    assert outcome.drift == []
    assert ("gemini", "gemini-2.0-flash") in outcome.registry.models


def test_free_registry_schema_drift_is_reported_from_realistic_payload():
    payload = deepcopy(fixture_body("omniroute_api_free_models"))
    payload["models"][0]["unexpectedFreeFlag"] = True
    payload["models"][1].pop("freeType")

    drift = validate_free_registry_payload(payload)

    assert ("models[0]", "unknown_field", "unexpectedFreeFlag") in drift
    assert ("models[1]", "missing_field", "freeType") in drift


def test_free_registry_sync_persists_snapshot_and_model_definitions(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    transport = _RegistryTransport()
    client = OmniRouteClient(base_url="https://omniroute.test", api_key="manage-key", transport=transport)

    outcome = sync_live_free_registry(client)
    snapshot_id = persist_free_registry_outcome(postgres_url, outcome)

    with psycopg.connect(postgres_url) as connection:
        snapshot = connection.execute(
            "SELECT raw_json FROM free_provider_registry_snapshots WHERE id = %s",
            (snapshot_id,),
        ).fetchone()
        model = connection.execute(
            """
            SELECT display_name, free_type, monthly_tokens
            FROM free_model_definitions
            WHERE provider_id = 'gemini' AND provider_model_id = 'gemini-2.0-flash'
            """
        ).fetchone()

    assert snapshot[0]["sync_outcome"]["model_count"] == outcome.model_count
    assert snapshot[0]["sync_outcome"]["drift"] == []
    assert model == ("Gemini 2.0 Flash", "recurring-daily", 25000000)
