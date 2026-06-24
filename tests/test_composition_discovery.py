from __future__ import annotations

import pytest

from tests._composition_support import (
    AASnapshot,
    Database,
    FreeRegistry,
    FreeRegistrySyncOutcome,
    MetadataSyncResult,
    MigrationRunner,
    Path,
    Repository,
    StageAdapters,
    build_startup_config,
    compose_runtime,
    run_composed_stage,
    seed_endpoint,
    valid_env,
)


@pytest.mark.spec("pipeline-orchestration::Matching writes endpoint bindings")
def test_model_matching_stage_writes_endpoint_binding(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    endpoint = seed_endpoint(repository)

    result = run_composed_stage(repository, "model-matching")

    with repository.database.transaction() as transaction:
        stored = repository.provider_endpoints.get(transaction, endpoint["id"])
        match_count = transaction.execute("SELECT count(*) AS total FROM model_match_candidates").fetchone()["total"]
    assert result.exit_code == 0
    assert result.stage_results[0]["details"]["effect"] == "repository_write"
    assert stored["canonical_model_id"] is not None
    assert match_count == 1


@pytest.mark.spec("model-matcher::Provider punctuation and tuning aliases")
def test_model_matching_stage_uses_existing_canonical_alias(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    endpoint = seed_endpoint(repository, model_id="nvidia/google/gemma-3n-e2b-it", provider_id="nvidia")
    with repository.database.transaction() as transaction:
        expected = repository.canonical_models.upsert(transaction, canonical_slug="gemma-3n-e2b")

    result = run_composed_stage(repository, "model-matching")

    with repository.database.transaction() as transaction:
        stored = repository.provider_endpoints.get(transaction, endpoint["id"])
        canonical = repository.canonical_models.get(transaction, stored["canonical_model_id"])
    assert result.exit_code == 0
    assert stored["canonical_model_id"] == expected["id"]
    assert canonical["canonical_slug"] == "gemma-3n-e2b"


@pytest.mark.spec("cli-and-operations::Registry command uses registry sync")
def test_sync_free_registry_command_uses_registry_adapter_and_persists(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    config = build_startup_config(valid_env(DATABASE_URL=postgres_url))
    calls = []

    def registry_sync(_client):
        calls.append("registry")
        return FreeRegistrySyncOutcome(
            registry=FreeRegistry(models={}, pool_budgets={}),
            free_models_payload={
                "models": [
                    {
                        "provider": "gemini",
                        "modelId": "gemini-2.0-flash",
                        "displayName": "Gemini 2.0 Flash",
                        "freeType": "recurring-daily",
                        "authType": "api_key",
                    }
                ]
            },
            rankings_payload={"providers": []},
            model_count=1,
            drift=[],
            errors=[],
        )

    runtime = compose_runtime(
        config,
        metadata_sync=lambda **_kwargs: MetadataSyncResult(
            candidates={}, aa_snapshot=AASnapshot(index_version="4.1", models=())
        ),
        adapters=StageAdapters(registry_sync=registry_sync),
    )

    result = runtime.run_command("sync-free-registry", object())

    repository = Repository(Database(postgres_url))
    with repository.database.transaction() as transaction:
        stored = transaction.execute("SELECT provider_id, provider_model_id FROM free_model_definitions").fetchall()
    assert result.exit_code == 0
    assert calls == ["registry"]
    assert [(row["provider_id"], row["provider_model_id"]) for row in stored] == [("gemini", "gemini-2.0-flash")]


@pytest.mark.spec("cli-and-operations::Provider scan command uses catalog scanner")
def test_scan_providers_command_uses_catalog_adapter_and_persists(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    config = build_startup_config(valid_env(DATABASE_URL=postgres_url))
    calls = []

    def catalog_scan(scanner, _client, omniroute_instance_id):
        calls.append((omniroute_instance_id, type(scanner).__name__))
        provider_id, account_id = scanner.upsert_provider_account(
            omniroute_instance_id=omniroute_instance_id,
            provider_slug="antigravity",
            provider_type="oauth",
            account_ref="acct-1",
        )
        scanner.store_snapshot(
            provider_id=provider_id,
            catalog={"models": [{"id": "antigravity/chat"}]},
            fetch_status="success",
        )
        scanner.upsert_endpoint(account_id, "antigravity/chat")
        return {"antigravity": "ok"}

    runtime = compose_runtime(
        config,
        metadata_sync=lambda **_kwargs: MetadataSyncResult(
            candidates={}, aa_snapshot=AASnapshot(index_version="4.1", models=())
        ),
        adapters=StageAdapters(catalog_scan=catalog_scan),
    )

    result = runtime.run_command("scan-providers", object())

    repository = Repository(Database(postgres_url))
    with repository.database.transaction() as transaction:
        endpoint = transaction.execute(
            """
            SELECT pe.provider_model_id
            FROM provider_endpoints pe
            JOIN provider_accounts pa ON pa.id = pe.provider_account_id
            JOIN providers p ON p.id = pa.provider_id
            WHERE p.omniroute_provider_id = 'antigravity'
            """
        ).fetchone()
    assert result.exit_code == 0
    assert calls == [(config.omniroute_url, "CatalogScanner")]
    assert endpoint["provider_model_id"] == "antigravity/chat"
