from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg

from fmo.accounts import group_quota_pools, usable_capacity
from fmo.candidates import build_free_candidates
from fmo.db import MigrationRunner
from fmo.matcher import MatchMethod, effective_context, match_model
from fmo.registry import sync_free_registry
from fmo.scanner import CatalogScanner, CatalogSnapshot, diff_catalogs, should_mark_removed


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


def test_diff_emits_events_and_false_removal_guard():
    previous = [{"id": "old", "name": "Old"}, {"id": "same", "name": "Same"}]
    current = [{"id": "same", "name": "Same"}, {"id": "new", "name": "New"}]

    events = diff_catalogs(previous, current)

    assert [event.kind for event in events] == ["provider_model_added", "provider_model_removed"]
    now = datetime.now(timezone.utc)
    assert not should_mark_removed([CatalogSnapshot(True, now - timedelta(minutes=10))], now)
    assert not should_mark_removed([CatalogSnapshot(False, now - timedelta(minutes=10)), CatalogSnapshot(True, now)], now)
    assert should_mark_removed([CatalogSnapshot(True, now - timedelta(minutes=6)), CatalogSnapshot(True, now)], now)


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


def test_matcher_order_forbidden_merges_confidence_and_context_override():
    exact = match_model("openai/gpt-4.1", canonical_slugs={"gpt-4.1"}, provider_catalog_ids=set())
    low = match_model("gpt-4.1-preview", canonical_slugs={"gpt-4.1"}, provider_catalog_ids=set())
    provider = match_model("anthropic/claude", canonical_slugs=set(), provider_catalog_ids={"anthropic/claude"})

    assert exact.method == MatchMethod.EXACT_SLUG
    assert exact.auto_use is True
    assert low.review_required is True
    assert provider.confidence == 0.98
    assert effective_context(canonical_context=128_000, provider_context=32_000) == 32_000
