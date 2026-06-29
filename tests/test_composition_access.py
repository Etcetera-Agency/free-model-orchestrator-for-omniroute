from __future__ import annotations

import pytest

from tests._composition_support import (
    CANONICAL_STAGE_NAMES,
    UTC,
    AASnapshot,
    AccountDiscoveryOpsClient,
    ComposedRuntime,
    Database,
    MetadataSyncResult,
    MigrationRunner,
    Path,
    PipelineOpsClient,
    PipelineRunner,
    Repository,
    StageAdapters,
    StageDependencies,
    argparse,
    build_canonical_stages,
    build_startup_config,
    compose_runtime,
    datetime,
    empty_adapters_with_stage_effects,
    empty_stage_adapters,
    hermes_inventory_fixture,
    run_composed_stage,
    run_rebalance_stages,
    seed_confirmed_llm_candidate,
    seed_endpoint,
    seed_free_registry_snapshot,
    timedelta,
    valid_env,
)


def test_lost_free_model_is_removed_from_existing_combo_on_rebalance(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    lost = seed_confirmed_llm_candidate(
        repository,
        model_id="lost-free",
        intelligence_index=70,
        connection_id="conn-provider-a",
    )
    kept = seed_confirmed_llm_candidate(
        repository,
        model_id="still-free",
        intelligence_index=75,
        connection_id="conn-provider-a",
    )
    with repository.database.transaction() as transaction:
        repository.roles.upsert(
            transaction,
            role_id="routing_fast",
            requirements={"capabilities": []},
            expected_load={"requests": 1},
            criticality=1,
        )
    now = datetime.now(UTC)
    seed_free_registry_snapshot(
        repository,
        models=[("provider-a", "lost-free"), ("provider-a", "still-free")],
        created_at=now - timedelta(days=1),
    )
    seed_free_registry_snapshot(repository, models=[("provider-a", "still-free")], created_at=now)
    client = PipelineOpsClient()
    client.combos = {"fmo-routing_fast": [str(lost["id"]), str(kept["id"])]}

    results = run_rebalance_stages(repository, client)

    assert [result.exit_code for result in results] == [0] * 9
    assert client.combos["fmo-routing_fast"] == [str(kept["id"])]
    assert not client.deleted_paths


def test_gained_free_model_is_added_to_existing_combo_on_rebalance(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    old = seed_confirmed_llm_candidate(
        repository,
        model_id="old-free",
        intelligence_index=70,
        connection_id="conn-provider-a",
    )
    new = seed_confirmed_llm_candidate(
        repository,
        model_id="new-free",
        intelligence_index=70,
        connection_id="conn-provider-a",
    )
    with repository.database.transaction() as transaction:
        repository.roles.upsert(
            transaction,
            role_id="routing_fast",
            requirements={"capabilities": []},
            expected_load={"requests": 1},
            criticality=1,
        )
    now = datetime.now(UTC)
    seed_free_registry_snapshot(repository, models=[("provider-a", "old-free")], created_at=now - timedelta(days=1))
    seed_free_registry_snapshot(
        repository,
        models=[("provider-a", "old-free"), ("provider-a", "new-free")],
        created_at=now,
    )
    client = PipelineOpsClient()
    client.combos = {"fmo-routing_fast": [str(old["id"])]}

    results = run_rebalance_stages(repository, client)

    assert [result.exit_code for result in results] == [0] * 9
    assert set(client.combos["fmo-routing_fast"]) == {str(old["id"]), str(new["id"])}
    assert not client.deleted_paths


@pytest.mark.spec("pipeline-orchestration::Full run calls production adapters")
def test_full_pipeline_runs_through_apply_and_audit(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    seed_endpoint(repository)
    with repository.database.transaction() as transaction:
        repository.roles.upsert(
            transaction,
            role_id="routing_fast",
            requirements={"capabilities": []},
            expected_load={"requests": 10},
            criticality=1,
        )
    dependencies = StageDependencies(
        repository=repository,
        omniroute_client=PipelineOpsClient(),
        config=build_startup_config(valid_env(DATABASE_URL=postgres_url)),
    )
    adapters = StageAdapters(
        registry_sync=empty_stage_adapters().registry_sync,
        catalog_scan=empty_stage_adapters().catalog_scan,
        account_discovery=empty_stage_adapters().account_discovery,
        hermes_inventory=lambda _config: hermes_inventory_fixture(),
    )
    stages = build_canonical_stages(
        dependencies=dependencies,
        metadata_sync=lambda **_kwargs: MetadataSyncResult(
            candidates={}, aa_snapshot=AASnapshot(index_version="4.1", models=())
        ),
        adapters=adapters,
    )

    result = PipelineRunner(repository, stages=stages).run(trigger="manual", run_type="full")

    assert result.exit_code == 0
    assert [record["name"] for record in result.stage_results] == [
        "external-metadata-sync",
        "free-candidate-discovery",
        "account-discovery",
        "model-matching",
        "access-classification",
        "probing",
        "telemetry-sync",
        "hermes-inventory",
        "role-lifecycle",
        "role-scoring",
        "demand-forecast",
        "audit",
    ]
    assert result.stage_results[-1]["status"] == "success"


@pytest.mark.spec("pipeline-orchestration::Account discovery persists account scopes")
def test_account_discovery_stage_persists_account_scopes(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    client = AccountDiscoveryOpsClient()

    result = run_composed_stage(repository, "account-discovery", client=client)

    with repository.database.transaction() as transaction:
        account_rows = transaction.execute(
            """
            SELECT omniroute_connection_id, quota_independence_status
            FROM provider_accounts
            ORDER BY omniroute_connection_id
            """
        ).fetchall()
        snapshot = transaction.execute(
            "SELECT independent_quota_pool_count, snapshot_json FROM account_discovery_snapshots"
        ).fetchone()
    assert result.exit_code == 0
    assert result.stage_results[0]["details"]["effect"] == "repository_write"
    assert client.get_calls[:2] == ["/api/providers", "/api/rate-limits"]
    assert [row["quota_independence_status"] for row in account_rows] == ["confirmed", "confirmed"]
    assert snapshot["snapshot_json"]["rate_limits_available"] is True


@pytest.mark.spec("account-discovery::Fingerprints create independent scopes")
def test_account_discovery_stage_persists_fingerprint_scopes(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    client = AccountDiscoveryOpsClient(
        connections=[
            {
                "id": "conn-fp",
                "provider": "provider-a",
                "enabled": True,
                "providerSpecificData": {"fingerprints": ["fp-a", "fp-b", "fp-c"]},
                "quota": 10,
            }
        ]
    )

    result = run_composed_stage(repository, "account-discovery", client=client)

    with repository.database.transaction() as transaction:
        rows = transaction.execute(
            """
            SELECT pa.omniroute_connection_id, pa.external_account_ref,
                   pa.metadata, pa.quota_independence_status
            FROM provider_accounts pa
            ORDER BY pa.omniroute_connection_id
            """
        ).fetchall()
        snapshot = transaction.execute(
            "SELECT independent_quota_pool_count FROM account_discovery_snapshots"
        ).fetchone()
    assert result.exit_code == 0
    assert len(rows) == 3
    assert {row["external_account_ref"] for row in rows} == {
        "provider-a:fingerprint:fp-a",
        "provider-a:fingerprint:fp-b",
        "provider-a:fingerprint:fp-c",
    }
    assert all(row["quota_independence_status"] == "confirmed" for row in rows)
    assert {row["metadata"]["parent_connection_id"] for row in rows} == {"conn-fp"}
    assert snapshot["independent_quota_pool_count"] == 3


@pytest.mark.spec("account-discovery::Fingerprint scopes feed allocation independently")
def test_fingerprint_pool_endpoints_feed_allocation_independently(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    endpoints = [
        seed_confirmed_llm_candidate(
            repository,
            model_id=f"fingerprint-model-{index}",
            intelligence_index=90 - index,
            remaining=5,
            connection_id=f"conn-fp#fingerprint:fp-{index}",
        )
        for index in range(3)
    ]
    with repository.database.transaction() as transaction:
        repository.roles.upsert(
            transaction,
            role_id="fingerprint_capacity",
            requirements={"capabilities": []},
            expected_load={"requests": 3},
            criticality=1,
        )
    run_composed_stage(repository, "role-scoring")
    run_composed_stage(repository, "demand-forecast")

    with repository.database.transaction() as transaction:
        target_pools = transaction.execute(
            """
            SELECT pa.external_account_ref AS name
            FROM provider_endpoints pe
            JOIN provider_accounts pa ON pa.id = pe.provider_account_id
            WHERE pe.id = ANY(%(endpoint_ids)s::uuid[])
            ORDER BY pa.external_account_ref
            """,
            {"endpoint_ids": [str(endpoint["id"]) for endpoint in endpoints]},
        ).fetchall()
    assert len({row["name"] for row in target_pools}) == len(endpoints)


@pytest.mark.spec("pipeline-orchestration::Unavailable rate-limit data stays conservative")
def test_account_discovery_stage_rate_limit_failure_stays_conservative(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    client = AccountDiscoveryOpsClient(rate_limits_fail=True)

    result = run_composed_stage(repository, "account-discovery", client=client)

    with repository.database.transaction() as transaction:
        statuses = [
            row["quota_independence_status"]
            for row in transaction.execute(
                "SELECT quota_independence_status FROM provider_accounts ORDER BY omniroute_connection_id"
            ).fetchall()
        ]
        snapshot = transaction.execute("SELECT snapshot_json FROM account_discovery_snapshots").fetchone()
    assert result.exit_code == 0
    assert statuses == ["assumed_shared", "assumed_shared"]
    assert snapshot["snapshot_json"]["rate_limits_available"] is False
    assert snapshot["snapshot_json"]["errors"][0]["status_code"] == 500


@pytest.mark.spec("pipeline-orchestration::Account discovery ordered before allocation inputs")
def test_canonical_pipeline_orders_account_discovery_before_quota_and_scoring():
    names = CANONICAL_STAGE_NAMES

    assert names.index("free-candidate-discovery") < names.index("account-discovery")
    assert names.index("account-discovery") < names.index("role-scoring")


@pytest.mark.spec("cli-and-operations::Discover-accounts command uses account discovery")
def test_discover_accounts_command_selects_account_discovery_stage(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    runtime = ComposedRuntime(
        repository=repository,
        omniroute_client=AccountDiscoveryOpsClient(),
        stages=build_canonical_stages(
            dependencies=StageDependencies(repository=repository, omniroute_client=AccountDiscoveryOpsClient()),
            metadata_sync=lambda **_kwargs: MetadataSyncResult(
                candidates={}, aa_snapshot=AASnapshot(index_version="4.1", models=())
            ),
        ),
        cron="0 4 * * *",
        llm_runtime=None,
        config=build_startup_config(valid_env(DATABASE_URL=postgres_url)),
    )

    result = runtime.run_command("discover-accounts", argparse.Namespace(dry_run=False))

    with repository.database.transaction() as transaction:
        stages = repository.runs.list(transaction)[0]["error_json"]["stages"]
        account_count = transaction.execute("SELECT count(*) AS total FROM provider_accounts").fetchone()["total"]
    assert result.exit_code == 0
    assert [stage["name"] for stage in stages] == ["account-discovery"]
    assert account_count == 2


@pytest.mark.spec("cli-and-operations::Dry-run runs the stage, not an unconditional success")
def test_full_dry_run_executes_runtime_without_omniroute_mutation(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    config = build_startup_config(valid_env(DATABASE_URL=postgres_url))
    client = PipelineOpsClient()
    metadata = MetadataSyncResult(candidates={}, aa_snapshot=AASnapshot(index_version="4.1", models=()))
    runtime = compose_runtime(
        config,
        metadata_sync=lambda **_kwargs: metadata,
        adapters=empty_adapters_with_stage_effects(),
    )
    runtime = ComposedRuntime(
        repository=runtime.repository,
        omniroute_client=client,
        stages=runtime.stages,
        cron=runtime.cron,
        llm_runtime=runtime.llm_runtime,
        config=runtime.config,
    )

    result = runtime.run_command("full", argparse.Namespace(dry_run=True))

    assert result.exit_code == 0
    assert result.combo_test_called is False
    assert client.calls == []
