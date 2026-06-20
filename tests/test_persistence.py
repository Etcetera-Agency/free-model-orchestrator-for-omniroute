from pathlib import Path

import pytest

from fmo.db import MigrationRunner
from fmo.persistence import Database, Repository
from fmo.registry import FreeRegistry, FreeRegistrySyncOutcome


@pytest.fixture()
def repository(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    database = Database(postgres_url)
    return Repository(database)


@pytest.mark.spec("persistence::Failed write rolls back")
@pytest.mark.spec("persistence::Failed write rolls back")
def test_failed_transaction_rolls_back_rows(repository):
    with pytest.raises(RuntimeError, match="boom"):
        with repository.database.transaction() as transaction:
            repository.runs.create(
                transaction,
                run_type="full",
                trigger="manual",
                status="running",
                code_version="test",
                config_hash="cfg",
            )
            raise RuntimeError("boom")

    with repository.database.transaction() as transaction:
        assert repository.runs.list(transaction) == []


@pytest.mark.spec("persistence::Committed write is durable")
@pytest.mark.spec("persistence::Committed write is durable")
def test_committed_transaction_is_visible_to_new_connection(repository):
    with repository.database.transaction() as transaction:
        run = repository.runs.create(
            transaction,
            run_type="full",
            trigger="manual",
            status="running",
            code_version="test",
            config_hash="cfg",
        )

    with repository.database.transaction() as transaction:
        assert repository.runs.get(transaction, run["id"]) == run


@pytest.mark.spec("persistence::Round-trip a provider endpoint")
@pytest.mark.spec("persistence::Round-trip a provider endpoint")
@pytest.mark.spec("data-model::Role reference type")
@pytest.mark.spec("data-model::Repository is the only writer")
@pytest.mark.spec("persistence::Sync writes metadata through the repository")
def test_domain_repository_round_trips(repository):
    with repository.database.transaction() as transaction:
        provider = repository.providers.upsert(
            transaction,
            omniroute_instance_id="local",
            omniroute_provider_id="openai",
            provider_type="api",
            display_name="OpenAI",
        )
        account = repository.provider_accounts.upsert(
            transaction,
            provider_id=provider["id"],
            omniroute_connection_id="conn-openai",
            external_account_ref="acct",
        )
        model = repository.canonical_models.upsert(
            transaction,
            canonical_slug="gpt-test",
            lab="OpenAI",
            family="gpt",
            version="test",
        )
        endpoint = repository.provider_endpoints.upsert(
            transaction,
            provider_account_id=account["id"],
            provider_model_id="gpt-test",
            model_type="chat",
            canonical_model_id=model["id"],
            lifecycle_status="active",
            access_status="allowed",
            capabilities={"chat": True},
            metadata_hash="endpoint-key",
        )
        snapshot = repository.snapshots.store_quota_source(
            transaction,
            source_url="https://quota.test/openai",
            source_type="docs",
            payload={"limit": "free"},
            title="Quota docs",
        )
        quota_rule = repository.quota_rules.upsert(
            transaction,
            provider_id=provider["id"],
            provider_account_id=account["id"],
            source_snapshot_id=snapshot["id"],
            model_pattern="gpt-*",
            access_type="free_quota",
            limits={"requests": 10},
            reset_policy={"interval": "day"},
            hard_stop_capable=True,
            confidence=0.9,
            status="active",
            rule_hash="quota-key",
        )
        probe = repository.probes.record(
            transaction,
            endpoint_id=endpoint["id"],
            suite_version="v1",
            probe_type="basic",
            request_hash="probe-key",
            passed=True,
            started_at="2026-06-18T00:00:00Z",
            finished_at="2026-06-18T00:00:01Z",
        )
        role = repository.roles.upsert(
            transaction,
            role_id="coder",
            requirements={"min_context": 8192},
            expected_load={"requests": 1},
            criticality=5,
        )
        score = repository.scores.upsert(
            transaction,
            role_id=role["id"],
            endpoint_id=endpoint["id"],
            score_version="v1",
            total_score=95,
            component_scores={"quality": 95},
            eligibility=True,
            input_state_hash="score-key",
        )
        plan = repository.allocation_plans.upsert(
            transaction,
            role_id=role["id"],
            status="planned",
            targets=[{"endpoint_id": str(endpoint["id"]), "weight": 1}],
            constraint_report={"ok": True},
            input_state_hash="plan-key",
        )
        combo = repository.combo_snapshots.upsert(
            transaction,
            role_id=role["id"],
            state_hash="combo-key",
            state_json={"models": ["gpt-test"]},
            phase="planned",
        )
        audit = repository.audit.record(
            transaction,
            entity_type="combo",
            entity_id=role["id"],
            action="planned",
            after_json=combo["state_json"],
            reason_codes=["test"],
        )

    with repository.database.transaction() as transaction:
        assert repository.provider_endpoints.get(transaction, endpoint["id"]) == endpoint
        assert repository.quota_rules.get(transaction, quota_rule["id"]) == quota_rule
        assert repository.probes.get(transaction, probe["id"]) == probe
        assert repository.scores.get(transaction, score["id"]) == score
        assert repository.allocation_plans.get(transaction, plan["id"]) == plan
        assert repository.combo_snapshots.get(transaction, combo["id"]) == combo
        assert repository.audit.get(transaction, audit["id"]) == audit


@pytest.mark.spec("persistence::Re-run does not duplicate")
@pytest.mark.spec("persistence::Re-run does not duplicate")
def test_idempotent_repository_writes_do_not_duplicate(repository):
    with repository.database.transaction() as transaction:
        provider = repository.providers.upsert(
            transaction,
            omniroute_instance_id="local",
            omniroute_provider_id="openai",
            provider_type="api",
        )
        account = repository.provider_accounts.upsert(
            transaction,
            provider_id=provider["id"],
            omniroute_connection_id="conn-openai",
        )
        endpoint = repository.provider_endpoints.upsert(
            transaction,
            provider_account_id=account["id"],
            provider_model_id="gpt-test",
            model_type="chat",
            lifecycle_status="active",
            access_status="allowed",
            metadata_hash="endpoint-key",
        )
        first_probe = repository.probes.record(
            transaction,
            endpoint_id=endpoint["id"],
            suite_version="v1",
            probe_type="basic",
            request_hash="same-key",
            passed=True,
            started_at="2026-06-18T00:00:00Z",
            finished_at="2026-06-18T00:00:01Z",
        )
        second_probe = repository.probes.record(
            transaction,
            endpoint_id=endpoint["id"],
            suite_version="v1",
            probe_type="basic",
            request_hash="same-key",
            passed=True,
            started_at="2026-06-18T00:00:00Z",
            finished_at="2026-06-18T00:00:01Z",
        )

    assert second_probe["id"] == first_probe["id"]
    with repository.database.transaction() as transaction:
        assert repository.probes.count_by_request_hash(transaction, "same-key") == 1


@pytest.mark.spec("persistence::Duplicate payload is one snapshot")
@pytest.mark.spec("persistence::Duplicate payload is one snapshot")
def test_content_hashed_snapshots_are_immutable_and_deduplicated(repository):
    payload = {"provider": "openai", "limits": {"requests": 10}}

    with repository.database.transaction() as transaction:
        first = repository.snapshots.store_quota_source(
            transaction,
            source_url="https://quota.test/openai",
            source_type="docs",
            payload=payload,
        )
        second = repository.snapshots.store_quota_source(
            transaction,
            source_url="https://quota.test/openai",
            source_type="docs",
            payload=payload,
        )

    assert second["id"] == first["id"]
    with repository.database.transaction() as transaction:
        assert repository.snapshots.count_by_hash(transaction, first["content_hash"]) == 1


@pytest.mark.spec("persistence::Round-trip a provider endpoint")
@pytest.mark.spec("provider-scanner::Catalog fetched before scan")
@pytest.mark.spec("provider-scanner::Successful catalog snapshot is stored")
@pytest.mark.spec("provider-scanner::Unchanged catalog is detected")
@pytest.mark.spec("persistence::Discovery repository writes remain idempotent")
def test_provider_catalog_repository_round_trips_and_deduplicates(repository):
    catalog = {"models": [{"id": "provider-a/chat"}]}

    with repository.database.transaction() as transaction:
        provider = repository.providers.upsert(
            transaction,
            omniroute_instance_id="local",
            omniroute_provider_id="provider-a",
            provider_type="oauth",
        )
        account = repository.provider_accounts.upsert(
            transaction,
            provider_id=provider["id"],
            omniroute_connection_id="provider-a-account",
            external_account_ref="provider-a-account",
        )
        snapshot = repository.provider_catalogs.store_snapshot(
            transaction,
            provider_id=provider["id"],
            catalog=catalog,
            fetch_status="success",
        )
        repeated = repository.provider_catalogs.store_snapshot(
            transaction,
            provider_id=provider["id"],
            catalog=catalog,
            fetch_status="success",
        )
        endpoint = repository.provider_endpoints.upsert(
            transaction,
            provider_account_id=account["id"],
            provider_model_id="provider-a/chat",
            lifecycle_status="discovered",
            access_status="access_pending",
        )

    assert snapshot["catalog_hash"] == repeated["catalog_hash"]
    assert repeated["is_unchanged"] is True
    with repository.database.transaction() as transaction:
        assert repository.provider_endpoints.get(transaction, endpoint["id"]) == endpoint


@pytest.mark.spec("persistence::Duplicate payload is one snapshot")
@pytest.mark.spec("persistence::Discovery repository writes remain idempotent")
@pytest.mark.spec("free-provider-registry-sync::Registry fetched before build")
@pytest.mark.spec("free-provider-registry-sync::Registry outcome is persisted")
def test_free_registry_repository_round_trips_model_definitions(repository):
    free_models_payload = {
        "models": [
            {
                "provider": "gemini",
                "modelId": "gemini-2.0-flash",
                "displayName": "Gemini 2.0 Flash",
                "freeType": "recurring-daily",
                "monthlyTokens": 25000000,
                "authType": "api_key",
            },
            {
                "provider": "browser-only",
                "modelId": "cookie-model",
                "freeType": "cookie",
                "authType": "web_cookie",
            },
        ]
    }
    outcome = FreeRegistrySyncOutcome(
        registry=FreeRegistry(models={}, pool_budgets={}),
        free_models_payload=free_models_payload,
        rankings_payload={"providers": []},
        model_count=2,
        drift=[],
        errors=[],
    )

    with repository.database.transaction() as transaction:
        snapshot = repository.free_registry.store_outcome(transaction, outcome=outcome)
        stored = transaction.execute(
            """
            SELECT provider_id, provider_model_id, display_name, free_type, monthly_tokens
            FROM free_model_definitions
            ORDER BY provider_id, provider_model_id
            """
        ).fetchall()

    assert snapshot["raw_json"]["sync_outcome"]["model_count"] == 2
    assert [(row["provider_id"], row["provider_model_id"]) for row in stored] == [("gemini", "gemini-2.0-flash")]
    assert stored[0]["display_name"] == "Gemini 2.0 Flash"
    assert int(stored[0]["monthly_tokens"]) == 25000000


@pytest.mark.spec("data-model::Repository is the only writer")
@pytest.mark.spec("persistence::Discovery writers use repository")
@pytest.mark.spec("provider-scanner::Scanner does not own SQL writes")
@pytest.mark.spec("free-provider-registry-sync::Registry writer does not own SQL writes")
def test_scanner_and_registry_modules_do_not_embed_table_sql():
    forbidden = (
        "psycopg",
        "INSERT INTO providers",
        "INSERT INTO provider_accounts",
        "INSERT INTO provider_catalog_snapshots",
        "INSERT INTO provider_endpoints",
        "INSERT INTO free_provider_registry_snapshots",
        "INSERT INTO free_model_definitions",
        "FROM provider_catalog_snapshots",
        "FROM free_provider_registry_snapshots",
        "FROM free_model_definitions",
    )

    for path in (Path("src/fmo/scanner.py"), Path("src/fmo/registry.py")):
        source = path.read_text()
        assert not any(sql in source for sql in forbidden), path
