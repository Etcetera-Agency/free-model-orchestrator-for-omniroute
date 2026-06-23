from pathlib import Path
from urllib.parse import urlsplit

import psycopg
import pytest

from _fixtures import fixture_body
from fmo.db import MigrationRunner
from fmo.omniroute import OmniRouteClient
from fmo.persistence import Database, Repository
from fmo.scanner import CatalogFetchError, CatalogScanner, scan_live_omniroute_catalogs


class _FixtureResponse:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self.headers = {}
        self._body = body

    def json(self):
        return self._body


class _CatalogTransport:
    def __init__(self, *, providers_body=None, models_status=200, models_body=None):
        self.providers_body = providers_body if providers_body is not None else fixture_body("omniroute_api_providers")
        self.models_status = models_status
        self.models_body = models_body if models_body is not None else fixture_body("omniroute_v1_models")
        self.requested_paths = []

    def request(self, method, url, headers=None, json=None, timeout=None):
        path = urlsplit(url).path
        self.requested_paths.append(path)
        if path == "/api/providers":
            return _FixtureResponse(200, self.providers_body)
        if path == "/v1/models":
            return _FixtureResponse(self.models_status, self.models_body)
        raise AssertionError(f"unexpected catalog request: {path}")


def _prepare_scanner(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    return CatalogScanner(Repository(Database(postgres_url)))


@pytest.mark.spec("provider-scanner::Catalog fetched before scan")
def test_live_catalog_scan_fetches_omniroute_fixtures_before_snapshot(postgres_url):
    scanner = _prepare_scanner(postgres_url)
    transport = _CatalogTransport()
    client = OmniRouteClient(base_url="https://omniroute.test", api_key="manage-key", transport=transport)

    result = scan_live_omniroute_catalogs(scanner, client, omniroute_instance_id="local")

    assert transport.requested_paths == ["/api/providers", "/v1/models"]
    antigravity = result["antigravity"]
    assert antigravity.fetch_status == "success"
    assert antigravity.model_count > 0

    with psycopg.connect(postgres_url) as connection:
        endpoint = connection.execute(
            """
            SELECT pe.provider_model_id, pe.lifecycle_status, pe.access_status, pe.probe_status
            FROM provider_endpoints pe
            JOIN provider_accounts pa ON pa.id = pe.provider_account_id
            JOIN providers p ON p.id = pa.provider_id
            WHERE p.omniroute_provider_id = 'antigravity'
            ORDER BY pe.provider_model_id
            LIMIT 1
            """
        ).fetchone()

    assert endpoint is not None
    assert endpoint[1:] == ("discovered", "access_pending", "not_run")


@pytest.mark.spec("account-discovery::Fingerprint pools feed allocation independently")
def test_live_catalog_scan_fans_models_out_to_fingerprint_accounts(postgres_url):
    scanner = _prepare_scanner(postgres_url)
    providers_body = fixture_body("omniroute_api_providers")
    provider = next(
        connection
        for connection in providers_body["connections"]
        if connection.get("provider") == "mimocode" and connection.get("providerSpecificData", {}).get("fingerprints")
    )
    models_body = {"object": "list", "data": [{"id": "mimocode/mimo-auto"}]}
    transport = _CatalogTransport(providers_body={"connections": [provider]}, models_body=models_body)
    client = OmniRouteClient(base_url="https://omniroute.test", api_key="manage-key", transport=transport)

    result = scan_live_omniroute_catalogs(scanner, client, omniroute_instance_id="local")

    assert result["mimocode"].fetch_status == "success"
    with psycopg.connect(postgres_url) as connection:
        rows = connection.execute(
            """
            SELECT pa.omniroute_connection_id, pa.external_account_ref, pe.provider_model_id
            FROM provider_accounts pa
            JOIN provider_endpoints pe ON pe.provider_account_id = pa.id
            JOIN providers p ON p.id = pa.provider_id
            WHERE p.omniroute_provider_id = 'mimocode'
            ORDER BY pa.external_account_ref
            """
        ).fetchall()

    assert len(rows) == 3
    assert {row[1] for row in rows} == {
        "mimocode:fingerprint:309782c1e8194398b096ecd9e38c68bb",
        "mimocode:fingerprint:ae68882817134ba3afad0cc4df9f1901",
        "mimocode:fingerprint:c40304c36c0c4698be90fa47063a5566",
    }
    assert {row[2] for row in rows} == {"mimocode/mimo-auto"}


@pytest.mark.spec("provider-scanner::Fetch failure does not overwrite")
def test_live_catalog_scan_records_failed_snapshots_without_overwriting_success(postgres_url):
    scanner = _prepare_scanner(postgres_url)
    provider_id, _account_id = scanner.upsert_provider_account(
        omniroute_instance_id="local",
        provider_slug="antigravity",
        provider_type="oauth",
        account_ref="existing-account",
    )
    previous = scanner.store_snapshot(
        provider_id=provider_id,
        catalog={"models": [{"id": "antigravity/previous"}]},
        fetch_status="success",
    )
    error_body = fixture_body("omniroute_provider_models_http_500")
    transport = _CatalogTransport(models_status=500, models_body=error_body)
    client = OmniRouteClient(base_url="https://omniroute.test", api_key="manage-key", transport=transport)

    result = scan_live_omniroute_catalogs(scanner, client, omniroute_instance_id="local")

    assert result["antigravity"].fetch_status == "error"
    assert isinstance(result["antigravity"].error, CatalogFetchError)

    with psycopg.connect(postgres_url) as connection:
        rows = connection.execute(
            """
            SELECT fetch_status, raw_payload
            FROM provider_catalog_snapshots
            WHERE provider_id = %s
            ORDER BY fetched_at, fetch_status
            """,
            (provider_id,),
        ).fetchall()

    assert previous.catalog_hash
    assert [row[0] for row in rows] == ["success", "error"]
    assert rows[-1][1]["error"]["reason"] == "http_error"


@pytest.mark.spec("free-candidate-discovery::models.dev invalid payload")
def test_live_catalog_fetch_rejects_invalid_models_payload(postgres_url):
    scanner = _prepare_scanner(postgres_url)
    transport = _CatalogTransport(models_body={"object": "list", "data": {"not": "a list"}})
    client = OmniRouteClient(base_url="https://omniroute.test", api_key="manage-key", transport=transport)

    result = scan_live_omniroute_catalogs(scanner, client, omniroute_instance_id="local")

    assert result["antigravity"].fetch_status == "error"
    assert result["antigravity"].error.reason == "invalid_payload"
