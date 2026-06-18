from pathlib import Path
from urllib.parse import urlsplit

import psycopg
import pytest

from fmo.db import MigrationRunner
from fmo.omniroute import OmniRouteClient
from fmo.scanner import CatalogFetchError, CatalogScanner, scan_live_omniroute_catalogs

from _fixtures import fixture_body


class _FixtureResponse:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self.headers = {}
        self._body = body

    def json(self):
        return self._body


class _CatalogTransport:
    def __init__(self, *, models_status=200, models_body=None):
        self.models_status = models_status
        self.models_body = models_body if models_body is not None else fixture_body("omniroute_v1_models")
        self.requested_paths = []

    def request(self, method, url, headers=None, json=None, timeout=None):
        path = urlsplit(url).path
        self.requested_paths.append(path)
        if path == "/api/providers":
            return _FixtureResponse(200, fixture_body("omniroute_api_providers"))
        if path == "/v1/models":
            return _FixtureResponse(self.models_status, self.models_body)
        raise AssertionError(f"unexpected catalog request: {path}")


def _prepare_scanner(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    return CatalogScanner(postgres_url)


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


def test_live_catalog_fetch_rejects_invalid_models_payload(postgres_url):
    scanner = _prepare_scanner(postgres_url)
    transport = _CatalogTransport(models_body={"object": "list", "data": {"not": "a list"}})
    client = OmniRouteClient(base_url="https://omniroute.test", api_key="manage-key", transport=transport)

    result = scan_live_omniroute_catalogs(scanner, client, omniroute_instance_id="local")

    assert result["antigravity"].fetch_status == "error"
    assert result["antigravity"].error.reason == "invalid_payload"
