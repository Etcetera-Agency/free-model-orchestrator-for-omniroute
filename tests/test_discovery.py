from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg
import pytest
import pytest

from fmo.accounts import group_quota_pools, usable_capacity
from fmo.candidates import build_free_candidates
from fmo.db import MigrationRunner
from fmo.matcher import MatchMethod, effective_context, match_model
from fmo.models_dev import MODELS_DEV_API_URL, ExternalMetadataError, fetch_models_dev_catalog, sync_models_dev_candidates
from fmo.registry import sync_free_registry
from fmo.scanner import CatalogScanner, CatalogSnapshot, diff_catalogs, should_mark_removed


class FakeResponse:
    def __init__(self, status_code, payload=None, json_error=None):
        self.status_code = status_code
        self.payload = payload
        self.json_error = json_error

    def json(self):
        if self.json_error:
            raise self.json_error
        return self.payload


class FakeHttpClient:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self.error:
            raise self.error
        return self.response


@pytest.mark.spec("free-candidate-discovery::Fetch models.dev api catalog")
def test_models_dev_fetches_api_json_and_syncs_candidates():
    payload = {"providers": {"p": {"models": {"m/free": {"cost": {"input": 0, "output": 0}}}}}}
    client = FakeHttpClient(FakeResponse(200, payload))

    catalog = fetch_models_dev_catalog(client=client, timeout=12)
    candidates = sync_models_dev_candidates(client=client)

    assert catalog == payload
    assert client.calls[0] == (MODELS_DEV_API_URL, {"timeout": 12})
    assert candidates[("p", "m/free")].reasons == ("multiple_signals",)


@pytest.mark.spec("free-candidate-discovery::models.dev real top-level provider-keyed body")
def test_models_dev_fetches_real_top_level_provider_keyed_catalog():
    from _fixtures import fixture_body

    body = fixture_body("models_dev_api_json")
    assert "providers" not in body  # real api.json has no wrapper
    client = FakeHttpClient(FakeResponse(200, body))

    catalog = fetch_models_dev_catalog(client=client)
    candidates = build_free_candidates(catalog)

    assert set(catalog) == {"providers"}
    assert catalog["providers"] is body
    assert ("alibaba-cn", "deepseek-r1-distill-qwen-1-5b") in candidates
    assert "zero_cost" in candidates[("alibaba-cn", "deepseek-r1-distill-qwen-1-5b")].reasons


@pytest.mark.spec("free-candidate-discovery::models.dev invalid payload")
def test_models_dev_rejects_error_body_without_provider_object():
    client = FakeHttpClient(FakeResponse(200, {"error": "rate_limited"}))

    try:
        fetch_models_dev_catalog(client=client)
    except ExternalMetadataError as exc:
        assert exc.reason == "invalid_payload"
    else:
        raise AssertionError("error body must be rejected as invalid payload")


@pytest.mark.spec("free-candidate-discovery::models.dev non-200")
def test_models_dev_fetcher_rejects_network_http_json_and_payload_errors():
    cases = [
        FakeHttpClient(error=TimeoutError("timeout")),
        FakeHttpClient(FakeResponse(503, {"providers": {}})),
        FakeHttpClient(FakeResponse(200, json_error=ValueError("bad json"))),
        FakeHttpClient(FakeResponse(200, [])),
        FakeHttpClient(FakeResponse(200, {"providers": []})),
    ]

    for client in cases:
        try:
            fetch_models_dev_catalog(client=client)
        except ExternalMetadataError as exc:
            assert exc.source == "models_dev"
        else:
            raise AssertionError("models.dev fetch should fail")


@pytest.mark.spec("free-candidate-discovery::Zero-cost provider offering")
@pytest.mark.spec("free-candidate-discovery::Free token in model id")
@pytest.mark.spec("free-candidate-discovery::Missing cost is not free")
def test_candidate_filter_uses_zero_cost_and_standalone_free_only():
    catalog = {
        "providers": {
            "zero": {"models": {"model-a": {"cost": {"input": 0, "output": 0}, "name": "Model A"}}},
            "missing": {"models": {"model-b": {"name": "Model B"}}},
            "free-id": {"models": {"vendor/free-chat": {"cost": {"input": 1, "output": 1}, "name": "Chat"}}},
            "false": {"models": {"carefree-chat": {"cost": {"input": 1, "output": 1}, "name": "Carefree"}}},
            "free-name": {"models": {"model-c": {"cost": {"input": 1, "output": 1}, "name": "Free Chat"}}},
        }
    }

    candidates = build_free_candidates(catalog)

    assert candidates[("zero", "model-a")].reasons == ("zero_cost",)
    assert candidates[("free-id", "vendor/free-chat")].reasons == ("free_in_model_id",)
    assert candidates[("free-name", "model-c")].reasons == ("free_in_display_name",)
    assert ("missing", "model-b") not in candidates
    assert ("false", "carefree-chat") not in candidates


@pytest.mark.spec("free-candidate-discovery::Same model differs by provider")
def test_candidate_cost_is_read_per_provider():
    catalog = {
        "providers": {
            "paid": {"models": {"same": {"cost": {"input": 0.01, "output": 0.02}}}},
            "free": {"models": {"same": {"cost": {"input": 0, "output": 0}}}},
        },
        "models": {"same": {"name": "Top-level has no cost authority"}},
    }

    candidates = build_free_candidates(catalog)

    assert ("free", "same") in candidates
    assert ("paid", "same") not in candidates


@pytest.mark.spec("free-candidate-discovery::False free token")
def test_candidate_free_token_rejects_unrelated_words_and_platform_names():
    catalog = {
        "providers": {
            "p": {
                "models": {
                    "freedom-chat": {"cost": {"input": 1, "output": 1}},
                    "carefree-chat": {"cost": {"input": 1, "output": 1}},
                    "freebsd-chat": {"cost": {"input": 1, "output": 1}},
                }
            }
        }
    }

    assert build_free_candidates(catalog) == {}


@pytest.mark.spec("free-candidate-discovery::Cost is not an object")
@pytest.mark.spec("free-candidate-discovery::Only input cost is zero")
def test_candidate_cost_non_dict_or_partial_zero_is_not_zero_cost():
    catalog = {
        "providers": {
            "p": {
                "models": {
                    "non-dict": {"cost": "free"},
                    "input-only": {"cost": {"input": 0, "output": 1}},
                }
            }
        }
    }

    assert build_free_candidates(catalog) == {}


@pytest.mark.spec("free-candidate-discovery::Multiple signals collapse")
def test_candidate_multiple_signals_are_collapsed():
    catalog = {"providers": {"p": {"models": {"vendor/free-chat": {"cost": {"input": 0, "output": 0}}}}}}

    candidates = build_free_candidates(catalog)

    assert candidates[("p", "vendor/free-chat")].reasons == ("multiple_signals",)


@pytest.mark.spec("provider-scanner::Catalog fetched before scan")
@pytest.mark.spec("provider-scanner::Fewer than two snapshots")
def test_scanner_snapshots_by_hash_and_skips_unchanged_diff(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    scanner = CatalogScanner(postgres_url)
    provider_id, account_id = scanner.upsert_provider_account(
        omniroute_instance_id="local",
        provider_slug="provider-a",
        provider_type="openai",
        account_ref="acc-a",
    )
    snapshot = scanner.store_snapshot(
        provider_id=provider_id,
        catalog={"models": [{"id": "m1"}]},
        fetch_status="success",
    )

    repeated = scanner.store_snapshot(
        provider_id=provider_id,
        catalog={"models": [{"id": "m1"}]},
        fetch_status="success",
    )

    assert snapshot.catalog_hash == repeated.catalog_hash
    assert repeated.is_unchanged is True
    assert scanner.upsert_endpoint(account_id, "m1").access_status == "access_pending"


@pytest.mark.spec("provider-scanner::New model discovered")
@pytest.mark.spec("provider-scanner::Omission too young")
@pytest.mark.spec("provider-scanner::Fewer than two snapshots")
def test_diff_emits_events_and_false_removal_guard():
    previous = [{"id": "old", "name": "Old"}, {"id": "same", "name": "Same"}]
    current = [{"id": "same", "name": "Same"}, {"id": "new", "name": "New"}]

    events = diff_catalogs(previous, current)

    assert [event.kind for event in events] == ["provider_model_added", "provider_model_removed"]
    now = datetime.now(timezone.utc)
    assert not should_mark_removed([CatalogSnapshot(True, now - timedelta(minutes=10))], now)
    assert not should_mark_removed([CatalogSnapshot(False, now - timedelta(minutes=10)), CatalogSnapshot(True, now)], now)
    assert not should_mark_removed([CatalogSnapshot(True, now - timedelta(minutes=6)), CatalogSnapshot(True, now)], now)
    assert should_mark_removed([CatalogSnapshot(True, now - timedelta(minutes=10)), CatalogSnapshot(True, now - timedelta(minutes=6))], now)


@pytest.mark.spec("provider-scanner::Failed snapshot not previous")
@pytest.mark.spec("provider-scanner::Not both snapshots successful")
def test_scanner_failed_snapshot_is_not_previous_for_unchanged_detection(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    scanner = CatalogScanner(postgres_url)
    provider_id, _account_id = scanner.upsert_provider_account(
        omniroute_instance_id="local",
        provider_slug="provider-a",
        provider_type="openai",
        account_ref="acc-a",
    )
    scanner.store_snapshot(provider_id=provider_id, catalog={"models": [{"id": "m1"}]}, fetch_status="success")
    failed = scanner.store_snapshot(provider_id=provider_id, catalog={"models": [{"id": "m2"}]}, fetch_status="error")
    repeated = scanner.store_snapshot(provider_id=provider_id, catalog={"models": [{"id": "m2"}]}, fetch_status="success")

    assert failed.is_unchanged is False
    assert repeated.is_unchanged is False


@pytest.mark.spec("account-discovery::Shared upstream account")
@pytest.mark.spec("account-discovery::Independent accounts")
def test_quota_grouping_counts_only_confirmed_independent_capacity():
    connections = [
        {"id": "a", "provider": "p", "upstream_account_id": "shared", "quota": 100, "status": "confirmed"},
        {"id": "b", "provider": "p", "upstream_account_id": "shared", "quota": 100, "status": "confirmed"},
        {"id": "c", "provider": "p", "upstream_account_id": "independent", "quota": 50, "status": "confirmed"},
        {"id": "d", "provider": "p", "quota": 100, "status": "assumed_shared"},
    ]

    pools = group_quota_pools(connections, previous_pools={"d": "last-confirmed"}, rate_limits_available=False)

    assert usable_capacity(pools) == 150
    assert pools["d"].pool_key == "last-confirmed"
    assert pools["d"].independence_status == "assumed_shared"


@pytest.mark.spec("account-discovery::Conflicting pool statuses")
def test_quota_grouping_conflicting_statuses_merge_to_unknown():
    pools = group_quota_pools(
        [
            {"id": "a", "provider": "p", "upstream_account_id": "shared", "quota": 100, "status": "confirmed"},
            {"id": "b", "provider": "p", "upstream_account_id": "shared", "quota": 100, "status": "assumed_shared"},
        ]
    )

    assert pools["shared"].independence_status == "unknown"


@pytest.mark.spec("account-discovery::Rate limits unavailable")
def test_quota_grouping_rate_limits_unavailable_reuses_previous_pool_key():
    pools = group_quota_pools(
        [{"id": "a", "provider": "p", "upstream_account_id": "new", "quota": 100, "status": "confirmed"}],
        previous_pools={"a": "previous"},
        rate_limits_available=False,
    )

    assert pools["a"].pool_key == "previous"


@pytest.mark.spec("account-discovery::Non-confirmed and duplicate capacity")
def test_usable_capacity_ignores_non_confirmed_and_duplicate_connection_ids():
    pools = group_quota_pools(
        [
            {"id": "a", "provider": "p", "upstream_account_id": "pool-a", "quota": 100, "status": "confirmed"},
            {"id": "a", "provider": "p", "upstream_account_id": "pool-a", "quota": 100, "status": "confirmed"},
            {"id": "b", "provider": "p", "upstream_account_id": "pool-b", "quota": 100, "status": "assumed_shared"},
        ]
    )

    assert usable_capacity(pools) == 100


@pytest.mark.spec("free-provider-registry-sync::Shared pool across models")
@pytest.mark.spec("free-provider-registry-sync::Web-cookie provider in registry")
@pytest.mark.spec("free-provider-registry-sync::Unscored provider")
def test_free_registry_deduplicates_pool_key_and_excludes_web_cookie():
    payload = {
        "models": [
            {"provider": "noauth", "modelId": "a", "monthlyTokens": 100, "poolKey": "shared", "authType": "none"},
            {"provider": "noauth", "modelId": "b", "monthlyTokens": 200, "poolKey": "shared", "authType": "none"},
            {"provider": "cookie", "modelId": "c", "monthlyTokens": 1000, "poolKey": "cookie", "authType": "web_cookie"},
        ]
    }

    registry = sync_free_registry(payload, rankings_payload={"providers": [{"provider": "rank-only"}]})

    assert registry.pool_budgets == {"shared": 200}
    assert ("cookie", "c") not in registry.models
    assert ("rank-only", None) not in registry.models


@pytest.mark.spec("model-matcher::Exact slug match")
@pytest.mark.spec("model-matcher::Base vs instruct")
@pytest.mark.spec("model-matcher::Low-confidence match")
@pytest.mark.spec("model-matcher::Smaller provider context")
def test_matcher_order_forbidden_merges_confidence_and_context_override():
    exact = match_model("openai/gpt-4.1", canonical_slugs={"gpt-4.1"}, provider_catalog_ids=set())
    low = match_model("gpt-4.1-preview", canonical_slugs={"gpt-4.1"}, provider_catalog_ids=set())
    provider = match_model("anthropic/claude", canonical_slugs=set(), provider_catalog_ids={"anthropic/claude"})

    assert exact.method == MatchMethod.EXACT_SLUG
    assert exact.auto_use is True
    assert low.review_required is True
    assert provider.confidence == 0.98
    assert effective_context(canonical_context=128_000, provider_context=32_000) == 32_000
