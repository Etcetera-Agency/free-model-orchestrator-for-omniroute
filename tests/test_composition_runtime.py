from __future__ import annotations

import pytest

from tests._composition_support import (
    CANONICAL_STAGE_NAMES,
    UTC,
    AAModelMetrics,
    AASnapshot,
    ComposedRuntime,
    Database,
    FakeInstructorClient,
    FakeOpenAIClient,
    FreeCandidate,
    FreeRegistry,
    FreeRegistrySyncOutcome,
    MetadataSyncResult,
    MigrationRunner,
    Path,
    PipelineOpsClient,
    QuotaClaimResponse,
    RecordingLlmRuntime,
    Repository,
    StageAdapters,
    StageDependencies,
    assert_success_has_declared_effect,
    build_canonical_stages,
    build_production_llm_runtime,
    build_startup_config,
    compose_runtime,
    datetime,
    effectful_success,
    empty_adapters_with_stage_effects,
    empty_stage_adapters,
    hermes_inventory_fixture,
    prepare_confirmed_endpoint,
    prepare_scored_endpoint,
    run_composed_stage,
    run_composed_stage_with_dependencies,
    seed_confirmed_llm_candidate,
    select_llm_model,
    valid_env,
)


@pytest.mark.spec("pipeline-orchestration::Probe respects confirmed free capacity")
@pytest.mark.spec("pipeline-orchestration::Probe persists results and excludes failures")
def test_probe_stage_gates_on_confirmed_capacity_and_persists_results(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    client = PipelineOpsClient()
    prepare_confirmed_endpoint(repository, client=client)

    result = run_composed_stage(repository, "probing", client=client)

    with repository.database.transaction() as transaction:
        probe = transaction.execute("SELECT passed, details FROM endpoint_probes").fetchone()
        endpoint = transaction.execute("SELECT probe_status FROM provider_endpoints").fetchone()
    assert result.exit_code == 0
    assert result.stage_results[0]["details"]["effect"] == "repository_write"
    assert client.calls[-1][0] == "/v1/providers/provider-a/chat/completions"
    assert client.calls[-1][2] == {"X-OmniRoute-No-Cache": "true"}
    assert probe["passed"] is True
    assert probe["details"]["reserved_capacity"] is True
    assert endpoint["probe_status"] == "passed"


@pytest.mark.spec("pipeline-orchestration::Telemetry sync writes normalized rows")
def test_telemetry_sync_stage_writes_normalized_health_rows(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    client = PipelineOpsClient()
    prepare_confirmed_endpoint(repository, client=client)

    result = run_composed_stage(repository, "telemetry-sync", client=client)

    with repository.database.transaction() as transaction:
        rows = transaction.execute(
            "SELECT granularity, sample_count, latency_p50_ms FROM endpoint_health_observations ORDER BY endpoint_id NULLS FIRST"
        ).fetchall()
    assert result.exit_code == 0
    assert result.stage_results[0]["details"]["effect"] == "repository_write"
    assert client.get_calls[-1] == "/api/usage/analytics"
    assert [(row["granularity"], row["sample_count"], row["latency_p50_ms"]) for row in rows] == [
        ("provider", 10, 120),
        ("provider", 5, 80),
    ]


@pytest.mark.spec("pipeline-orchestration::Quota sync writes remaining-quota state")
def test_quota_sync_stage_writes_remaining_quota_state(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    client = PipelineOpsClient()
    prepare_confirmed_endpoint(repository, client=client)

    result = run_composed_stage(repository, "quota-sync", client=client)

    with repository.database.transaction() as transaction:
        observation = transaction.execute(
            "SELECT limit_value, used_value, remaining_value FROM quota_observations"
        ).fetchone()
        access = transaction.execute("SELECT effective_remaining FROM endpoint_access_states").fetchone()
    assert result.exit_code == 0
    assert result.stage_results[0]["details"]["effect"] == "repository_write"
    assert client.get_calls[-1] == "/api/usage/quota"
    assert float(observation["limit_value"]) == 200_000.0
    assert float(observation["used_value"]) == 80_000.0
    assert float(observation["remaining_value"]) == 120_000.0
    assert access["effective_remaining"]["requests"] == 100.0


@pytest.mark.spec("hermes-inventory::Inventory persisted from the selected mode")
@pytest.mark.spec("hermes-inventory::Inspector is prompt-only")
@pytest.mark.spec("pipeline-orchestration::Inventory precedes scoring")
@pytest.mark.spec("pipeline-orchestration::Schedule change refreshes forecast inputs")
def test_hermes_inventory_stage_uses_selected_adapter_and_persists_prompt_only_forecast(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    config = build_startup_config(
        valid_env(DATABASE_URL=postgres_url, HERMES_INVENTORY_MODE="command", HERMES_INVENTORY_COMMAND="inventory")
    )
    llm_runtime = RecordingLlmRuntime()
    dependencies = StageDependencies(
        repository=repository,
        omniroute_client=PipelineOpsClient(),
        config=config,
        llm_runtime=llm_runtime,
        hermes_inventory_adapter=lambda received: (
            hermes_inventory_fixture() if received.hermes_inventory_mode == "command" else None
        ),
    )

    result = run_composed_stage_with_dependencies(repository, "hermes-inventory", dependencies)

    with repository.database.transaction() as transaction:
        role = transaction.execute(
            "SELECT id, expected_load, role_lifecycle_status FROM roles WHERE id = 'routing_fast'"
        ).fetchone()
        consumer = transaction.execute("SELECT consumer_key, calls_per_run FROM role_consumers").fetchone()
        inventory_run = transaction.execute(
            "SELECT source_mode, status, roles_found, routines_found FROM hermes_inventory_runs"
        ).fetchone()
    assert result.exit_code == 0
    assert result.stage_results[0]["details"]["effect"] == "repository_write"
    assert role["expected_load"]["requests"] == 25
    assert role["role_lifecycle_status"] == "bootstrap_pending"
    assert consumer["consumer_key"] == "a1b2c3d4e5f6"
    assert float(consumer["calls_per_run"]) == 12.0
    assert inventory_run["source_mode"] == "command"
    assert inventory_run["status"] == "completed"
    assert inventory_run["roles_found"] == 2
    assert inventory_run["routines_found"] == 1
    assert llm_runtime.calls == [
        {
            "site": "hermes-inspector",
            "context": {
                "prompt": (
                    "Hermes inventory forecast request\n"
                    "Changes:\n"
                    "Consumers:\n"
                    "coding-combo cron_job a1b2c3d4e5f6 0 2 * * * 12"
                )
            },
            "response_model": "InspectorForecastResponse",
        }
    ]


@pytest.mark.spec("hermes-inventory::Missing Hermes env fails closed")
def test_hermes_inventory_stage_missing_env_fails_closed(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    config = build_startup_config(
        valid_env(
            DATABASE_URL=postgres_url,
            HERMES_INVENTORY_MODE="command",
            HERMES_INVENTORY_COMMAND="",
        )
    )
    dependencies = StageDependencies(repository=repository, omniroute_client=PipelineOpsClient(), config=config)

    result = run_composed_stage_with_dependencies(repository, "hermes-inventory", dependencies)

    with repository.database.transaction() as transaction:
        role_count = transaction.execute("SELECT count(*) AS total FROM roles").fetchone()["total"]
    assert result.exit_code == 3
    assert role_count == 0


@pytest.mark.spec("dynamic-role-lifecycle::Removed role enters grace")
@pytest.mark.spec("dynamic-role-lifecycle::Role reactivated within grace")
@pytest.mark.spec("dynamic-role-lifecycle::New role bootstrapped")
@pytest.mark.spec("pipeline-orchestration::Reconcile and forecast precede allocation")
def test_role_lifecycle_reconciles_removed_reactivated_and_new_roles(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    with repository.database.transaction() as transaction:
        repository.roles.upsert(
            transaction,
            role_id="removed",
            requirements={"capabilities": []},
            expected_load={"requests": 1},
            criticality=1,
        )
        repository.roles.upsert(
            transaction,
            role_id="back",
            requirements={"capabilities": []},
            expected_load={"requests": 1},
            criticality=1,
        )
        transaction.execute("UPDATE roles SET role_lifecycle_status = 'retiring' WHERE id = 'back'")
        repository.roles.upsert(
            transaction,
            role_id="new",
            requirements={"capabilities": []},
            expected_load={"requests": 1},
            criticality=1,
        )
        transaction.execute("UPDATE roles SET role_lifecycle_status = 'bootstrap_pending' WHERE id = 'new'")
        for role_id in ("back", "new"):
            repository.role_consumers.upsert(
                transaction,
                role_id=role_id,
                consumer_type="cron_job",
                consumer_key=f"{role_id}-consumer",
                cadence="0 4 * * *",
                calls_per_run=2,
                source_hash="test",
            )

    result = run_composed_stage(repository, "role-lifecycle")

    with repository.database.transaction() as transaction:
        rows = transaction.execute("SELECT id, role_lifecycle_status, missing_since FROM roles ORDER BY id").fetchall()
    by_role = {row["id"]: row for row in rows}
    assert result.exit_code == 0
    assert by_role["removed"]["role_lifecycle_status"] == "retiring"
    assert by_role["removed"]["missing_since"] is not None
    assert by_role["back"]["role_lifecycle_status"] == "active"
    assert by_role["new"]["role_lifecycle_status"] == "bootstrap_pending"


@pytest.mark.spec("pipeline-orchestration::Scoring persists per-role scores")
def test_role_scoring_stage_persists_per_role_scores(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    client = PipelineOpsClient()
    prepare_scored_endpoint(repository, client=client)

    result = run_composed_stage(repository, "role-scoring", client=client)

    with repository.database.transaction() as transaction:
        score = transaction.execute("SELECT role_id, eligibility, total_score FROM role_scores").fetchone()
    assert result.exit_code == 0
    assert result.stage_results[0]["details"]["effect"] == "repository_write"
    assert score["role_id"] == "routing_fast"
    assert score["eligibility"] is True
    assert float(score["total_score"]) > 0


@pytest.mark.spec("role-scorer::AA quality drives the benchmark component")
def test_role_scoring_stage_uses_aa_quality_for_benchmark_component(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    for model_id, index in [("quality-low", 20), ("quality-mid", 50), ("quality-high", 90)]:
        seed_confirmed_llm_candidate(repository, model_id=model_id, intelligence_index=index)
    with repository.database.transaction() as transaction:
        repository.roles.upsert(
            transaction,
            role_id="quality_order",
            requirements={"capabilities": []},
            expected_load={"requests": 1},
            criticality=1,
        )

    run_composed_stage(repository, "role-scoring")

    with repository.database.transaction() as transaction:
        rows = transaction.execute(
            """
            SELECT pe.provider_model_id, rs.total_score, rs.component_scores
            FROM role_scores rs
            JOIN provider_endpoints pe ON pe.id = rs.endpoint_id
            WHERE rs.role_id = 'quality_order'
            ORDER BY pe.provider_model_id
            """
        ).fetchall()
    scores = {row["provider_model_id"]: row for row in rows}
    assert (
        scores["quality-low"]["component_scores"]["benchmark_fit"]
        < scores["quality-mid"]["component_scores"]["benchmark_fit"]
    )
    assert (
        scores["quality-mid"]["component_scores"]["benchmark_fit"]
        < scores["quality-high"]["component_scores"]["benchmark_fit"]
    )
    assert float(scores["quality-low"]["total_score"]) < float(scores["quality-high"]["total_score"])


@pytest.mark.spec("role-scorer::Latency component uses the latency source priority")
def test_role_scoring_stage_uses_latency_source_priority(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    fast = seed_confirmed_llm_candidate(repository, model_id="latency-endpoint", intelligence_index=80, aa_latency=8)
    aa_only = seed_confirmed_llm_candidate(
        repository,
        model_id="latency-aa",
        intelligence_index=80,
        aa_latency=2,
        provider_id="provider-b",
        connection_id="pool-b",
    )
    with repository.database.transaction() as transaction:
        repository.roles.upsert(
            transaction,
            role_id="latency_role",
            requirements={"capabilities": []},
            expected_load={"requests": 1},
            criticality=1,
        )
        provider = transaction.execute(
            """
            SELECT pa.provider_id
            FROM provider_endpoints pe
            JOIN provider_accounts pa ON pa.id = pe.provider_account_id
            WHERE pe.id = %(endpoint_id)s
            """,
            {"endpoint_id": fast["id"]},
        ).fetchone()
        transaction.execute(
            """
            INSERT INTO endpoint_health_observations (
              endpoint_id, granularity, status, latency_p95_ms, sample_count, observed_at
            )
            VALUES (%(endpoint_id)s, 'model', 'active', 100, 10, now() + interval '1 minute')
            """,
            {"endpoint_id": fast["id"]},
        )
        transaction.execute(
            """
            INSERT INTO endpoint_health_observations (
              provider_id, granularity, status, latency_p95_ms, sample_count, observed_at
            )
            VALUES (%(provider_id)s, 'provider', 'active', 9000, 10, now() + interval '1 minute')
            """,
            {"provider_id": provider["provider_id"]},
        )

    run_composed_stage(repository, "role-scoring")

    with repository.database.transaction() as transaction:
        rows = transaction.execute(
            """
            SELECT pe.provider_model_id, rs.component_scores
            FROM role_scores rs
            JOIN provider_endpoints pe ON pe.id = rs.endpoint_id
            WHERE rs.role_id = 'latency_role'
            """
        ).fetchall()
    components = {row["provider_model_id"]: row["component_scores"] for row in rows}
    assert components["latency-endpoint"]["latency"] == pytest.approx(0.99)
    assert components["latency-aa"]["latency"] == pytest.approx(0.8)
    assert str(aa_only["id"])


@pytest.mark.spec("role-scorer::Health and stability come from telemetry observations")
def test_role_scoring_stage_uses_health_observation_components(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    healthy = seed_confirmed_llm_candidate(repository, model_id="healthy-model", intelligence_index=80)
    degraded = seed_confirmed_llm_candidate(repository, model_id="degraded-model", intelligence_index=80)
    with repository.database.transaction() as transaction:
        repository.roles.upsert(
            transaction,
            role_id="health_role",
            requirements={"capabilities": []},
            expected_load={"requests": 1},
            criticality=1,
        )
        transaction.execute(
            """
            INSERT INTO endpoint_health_observations (
              endpoint_id, granularity, status, success_rate, sample_count, observed_at
            )
            VALUES (%(endpoint_id)s, 'model', 'active', 1.0, 10, now() + interval '1 minute')
            """,
            {"endpoint_id": healthy["id"]},
        )
        transaction.execute(
            """
            INSERT INTO endpoint_health_observations (
              endpoint_id, granularity, status, error_rate, sample_count, observed_at
            )
            VALUES (%(endpoint_id)s, 'model', 'degraded', 0.5, 1, now() + interval '1 minute')
            """,
            {"endpoint_id": degraded["id"]},
        )

    run_composed_stage(repository, "role-scoring")

    with repository.database.transaction() as transaction:
        rows = transaction.execute(
            """
            SELECT pe.provider_model_id, rs.component_scores
            FROM role_scores rs
            JOIN provider_endpoints pe ON pe.id = rs.endpoint_id
            WHERE rs.role_id = 'health_role'
            """
        ).fetchall()
    components = {row["provider_model_id"]: row["component_scores"] for row in rows}
    # success_rate/error_rate are fractions in [0, 1]; a full 1.0 success_rate
    # must map to a full health component, not a /100-scaled 0.01.
    assert components["healthy-model"]["health"] == pytest.approx(1.0)
    assert components["degraded-model"]["health"] == pytest.approx(0.5)
    assert components["degraded-model"]["health"] < components["healthy-model"]["health"]
    assert components["degraded-model"]["stability"] < components["healthy-model"]["stability"]


@pytest.mark.spec("role-scorer::Missing AA metrics apply the uncertainty penalty")
def test_role_scoring_stage_penalizes_missing_aa_metrics(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    endpoint = seed_confirmed_llm_candidate(repository, model_id="missing-aa", intelligence_index=80)
    with repository.database.transaction() as transaction:
        transaction.execute("DELETE FROM artificial_analysis_model_metrics")
        repository.roles.upsert(
            transaction,
            role_id="missing_aa_role",
            requirements={"capabilities": []},
            expected_load={"requests": 1},
            criticality=1,
        )

    run_composed_stage(repository, "role-scoring")

    with repository.database.transaction() as transaction:
        score = transaction.execute(
            "SELECT component_scores, total_score FROM role_scores WHERE endpoint_id = %(endpoint_id)s",
            {"endpoint_id": endpoint["id"]},
        ).fetchone()
    assert score["component_scores"]["benchmark_fit"] == 0.0
    assert float(score["total_score"]) == pytest.approx(3.7)


@pytest.mark.spec("role-scorer::Below context minimum rejected in scoring")
@pytest.mark.spec("context-window-eligibility::Below minimum")
@pytest.mark.spec("pipeline-orchestration::Scoring stage drops below-context endpoint")
def test_role_scoring_stage_rejects_below_context_endpoint(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    endpoint = seed_confirmed_llm_candidate(
        repository, model_id="tiny-context", intelligence_index=80, context_window=4096
    )
    with repository.database.transaction() as transaction:
        repository.roles.upsert(
            transaction,
            role_id="long_context",
            requirements={"capabilities": [], "minimum_context_window": 8192},
            expected_load={"requests": 1},
            criticality=1,
        )

    result = run_composed_stage(repository, "role-scoring")

    with repository.database.transaction() as transaction:
        score = transaction.execute("SELECT eligibility, rejection_reasons FROM role_scores").fetchone()
    assert result.exit_code == 0
    assert score["eligibility"] is False
    assert score["rejection_reasons"] == ["context"]
    assert endpoint["id"]


@pytest.mark.spec("context-window-eligibility::Unknown context, no override")
def test_role_scoring_stage_rejects_unknown_context_unless_role_overrides(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    seed_confirmed_llm_candidate(repository, model_id="unknown-context", intelligence_index=80, context_window=None)
    with repository.database.transaction() as transaction:
        repository.roles.upsert(
            transaction,
            role_id="strict_context",
            requirements={"capabilities": [], "minimum_context_window": 8192},
            expected_load={"requests": 1},
            criticality=1,
        )
        repository.roles.upsert(
            transaction,
            role_id="override_context",
            requirements={"capabilities": [], "minimum_context_window": 8192, "manual_context_override": True},
            expected_load={"requests": 1},
            criticality=1,
        )

    run_composed_stage(repository, "role-scoring")

    with repository.database.transaction() as transaction:
        scores = {
            row["role_id"]: (row["eligibility"], row["rejection_reasons"])
            for row in transaction.execute("SELECT role_id, eligibility, rejection_reasons FROM role_scores").fetchall()
        }
    assert scores["strict_context"] == (False, ["context"])
    assert scores["override_context"][0] is True


@pytest.mark.spec("role-scorer::Below quality gate rejected in scoring")
@pytest.mark.spec("quality-gate::Below the gate")
@pytest.mark.spec("pipeline-orchestration::Scoring stage drops below-gate endpoint")
def test_role_scoring_stage_rejects_endpoint_below_quality_gate(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    seed_confirmed_llm_candidate(repository, model_id="low-quality", intelligence_index=40)
    with repository.database.transaction() as transaction:
        repository.roles.upsert(
            transaction,
            role_id="quality_role",
            requirements={"capabilities": []},
            expected_load={"requests": 1},
            criticality=1,
        )
        transaction.execute(
            """
            UPDATE roles
            SET minimum_quality_metric = 'intelligence_index',
                minimum_quality_value = 80,
                quality_gate_index_version = '4.1'
            WHERE id = 'quality_role'
            """
        )

    run_composed_stage(repository, "role-scoring")

    with repository.database.transaction() as transaction:
        score = transaction.execute("SELECT eligibility, rejection_reasons FROM role_scores").fetchone()
    assert score["eligibility"] is False
    assert score["rejection_reasons"] == ["quality_gate:below_gate"]


@pytest.mark.spec("quality-gate::Endpoint above the band is excluded")
def test_role_scoring_stage_rejects_endpoint_above_quality_band(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    seed_confirmed_llm_candidate(repository, model_id="too-smart", intelligence_index=75)
    with repository.database.transaction() as transaction:
        repository.roles.upsert(
            transaction,
            role_id="banded_role",
            requirements={"capabilities": []},
            expected_load={"requests": 1},
            criticality=1,
            minimum_quality_metric="intelligence_index",
            minimum_quality_value=40,
            maximum_quality_metric="intelligence_index",
            maximum_quality_value=60,
            quality_gate_index_version="4.1",
        )

    run_composed_stage(repository, "role-scoring")

    with repository.database.transaction() as transaction:
        score = transaction.execute("SELECT eligibility, rejection_reasons FROM role_scores").fetchone()
    assert score["eligibility"] is False
    assert score["rejection_reasons"] == ["quality_gate:above_band"]


@pytest.mark.spec("quality-gate::Band bounds are set once from the seed anchor")
def test_role_scoring_stage_sets_quality_band_from_single_seed_and_keeps_existing_band(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    seed = seed_confirmed_llm_candidate(repository, model_id="seed-mid", intelligence_index=60)
    other = seed_confirmed_llm_candidate(repository, model_id="other-high", intelligence_index=80)
    with repository.database.transaction() as transaction:
        repository.roles.upsert(
            transaction,
            role_id="routing_fast",
            requirements={"capabilities": []},
            expected_load={"requests": 1},
            criticality=1,
        )
    client = PipelineOpsClient()
    client.combos["fmo-routing_fast"] = [str(seed["id"])]

    run_composed_stage(repository, "role-scoring", client=client)
    client.combos["fmo-routing_fast"] = [str(seed["id"]), str(other["id"])]
    with repository.database.transaction() as transaction:
        transaction.execute(
            "UPDATE roles SET minimum_quality_value = 55, maximum_quality_value = 65 WHERE id = 'routing_fast'"
        )
    run_composed_stage(repository, "role-scoring", client=client)

    with repository.database.transaction() as transaction:
        role = transaction.execute(
            "SELECT minimum_quality_value, maximum_quality_value FROM roles WHERE id = 'routing_fast'"
        ).fetchone()
    assert float(role["minimum_quality_value"]) == 55
    assert float(role["maximum_quality_value"]) == 65


@pytest.mark.spec("quality-gate::Re-seeding re-anchors the band")
def test_role_scoring_stage_reanchors_when_combo_is_stripped_to_single_member(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    first = seed_confirmed_llm_candidate(repository, model_id="seed-low", intelligence_index=50)
    second = seed_confirmed_llm_candidate(repository, model_id="seed-high", intelligence_index=75)
    with repository.database.transaction() as transaction:
        repository.roles.upsert(
            transaction,
            role_id="routing_fast",
            requirements={"capabilities": []},
            expected_load={"requests": 1},
            criticality=1,
        )
    client = PipelineOpsClient()
    client.combos["fmo-routing_fast"] = [str(first["id"])]
    run_composed_stage(repository, "role-scoring", client=client)
    client.combos["fmo-routing_fast"] = [str(second["id"])]
    run_composed_stage(repository, "role-scoring", client=client)

    with repository.database.transaction() as transaction:
        role = transaction.execute(
            "SELECT minimum_quality_value, maximum_quality_value FROM roles WHERE id = 'routing_fast'"
        ).fetchone()
    assert float(role["minimum_quality_value"]) <= 75 <= float(role["maximum_quality_value"])
    assert float(role["minimum_quality_value"]) > 50


@pytest.mark.spec("quality-gate::Paid seed anchors but is not a member")
def test_paid_seed_sets_anchor_but_is_excluded_from_allocated_members(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    paid_seed = seed_confirmed_llm_candidate(repository, model_id="paid-seed", intelligence_index=70)
    free_member = seed_confirmed_llm_candidate(repository, model_id="free-member", intelligence_index=68)
    with repository.database.transaction() as transaction:
        transaction.execute(
            "UPDATE provider_endpoints SET access_status = 'paid' WHERE id = %(id)s", {"id": paid_seed["id"]}
        )
        transaction.execute("DELETE FROM endpoint_access_states WHERE endpoint_id = %(id)s", {"id": paid_seed["id"]})
        repository.roles.upsert(
            transaction,
            role_id="routing_fast",
            requirements={"capabilities": []},
            expected_load={"requests": 1},
            criticality=1,
        )
    client = PipelineOpsClient()
    client.combos["fmo-routing_fast"] = [str(paid_seed["id"])]

    run_composed_stage(repository, "role-scoring", client=client)
    run_composed_stage(repository, "demand-forecast", client=client)
    run_composed_stage(repository, "allocation", client=client)

    with repository.database.transaction() as transaction:
        role = transaction.execute(
            "SELECT minimum_quality_value, maximum_quality_value FROM roles WHERE id = 'routing_fast'"
        ).fetchone()
        plan = transaction.execute(
            "SELECT targets FROM allocation_plans WHERE role_id = 'routing_fast' ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
    target_ids = [target["endpoint_id"] for target in plan["targets"]]
    assert float(role["minimum_quality_value"]) <= 70 <= float(role["maximum_quality_value"])
    assert str(paid_seed["id"]) not in target_ids
    assert str(free_member["id"]) in target_ids


@pytest.mark.spec("quality-gate::Missing gate metric")
def test_role_scoring_stage_rejects_unverifiable_quality_unless_role_allows(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    seed_confirmed_llm_candidate(repository, model_id="missing-coding", intelligence_index=90, coding_index=None)
    with repository.database.transaction() as transaction:
        for role_id, requirements in [
            ("strict_quality", {"capabilities": []}),
            ("allow_unverified", {"capabilities": [], "allow_unverified_quality_gate": True}),
        ]:
            repository.roles.upsert(
                transaction, role_id=role_id, requirements=requirements, expected_load={"requests": 1}, criticality=1
            )
        transaction.execute(
            """
            UPDATE roles
            SET minimum_quality_metric = 'coding_index',
                minimum_quality_value = 50,
                quality_gate_index_version = '4.1'
            """
        )

    run_composed_stage(repository, "role-scoring")

    with repository.database.transaction() as transaction:
        scores = {
            row["role_id"]: (row["eligibility"], row["rejection_reasons"])
            for row in transaction.execute("SELECT role_id, eligibility, rejection_reasons FROM role_scores").fetchall()
        }
    assert scores["strict_quality"] == (False, ["quality_gate:unverifiable"])
    assert scores["allow_unverified"][0] is True


@pytest.mark.spec("quality-gate::Major index change")
@pytest.mark.spec("pipeline-orchestration::Index-version mismatch keeps current combo")
def test_quality_gate_index_version_mismatch_skips_new_allocation_plan(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    seed_confirmed_llm_candidate(repository, model_id="stale-index", intelligence_index=90, aa_index_version="4.1")
    with repository.database.transaction() as transaction:
        repository.roles.upsert(
            transaction,
            role_id="stale_gate",
            requirements={"capabilities": []},
            expected_load={"requests": 1},
            criticality=1,
        )
        transaction.execute(
            """
            UPDATE roles
            SET minimum_quality_metric = 'intelligence_index',
                minimum_quality_value = 80,
                quality_gate_index_version = '5.0'
            WHERE id = 'stale_gate'
            """
        )

    run_composed_stage(repository, "role-scoring")
    allocation = run_composed_stage(repository, "allocation")

    with repository.database.transaction() as transaction:
        score = transaction.execute("SELECT eligibility, rejection_reasons FROM role_scores").fetchone()
        plan_count = transaction.execute(
            "SELECT count(*) AS total FROM allocation_plans WHERE role_id = 'stale_gate'"
        ).fetchone()["total"]
    assert score["eligibility"] is False
    assert score["rejection_reasons"] == ["quality_gate:needs_recalibration"]
    assert allocation.exit_code == 0
    assert plan_count == 0


@pytest.mark.spec("pipeline-orchestration::Scoring stage drops below-gate endpoint")
def test_explain_endpoint_reports_quality_gate_rejection(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    endpoint = seed_confirmed_llm_candidate(repository, model_id="diagnostic-low-quality", intelligence_index=40)
    with repository.database.transaction() as transaction:
        repository.roles.upsert(
            transaction,
            role_id="quality_role",
            requirements={"capabilities": []},
            expected_load={"requests": 1},
            criticality=1,
        )
        transaction.execute(
            """
            UPDATE roles
            SET minimum_quality_metric = 'intelligence_index',
                minimum_quality_value = 80,
                quality_gate_index_version = '4.1'
            WHERE id = 'quality_role'
            """
        )
    run_composed_stage(repository, "role-scoring")
    runtime = ComposedRuntime(
        repository=repository,
        omniroute_client=PipelineOpsClient(),
        stages=[],
        cron="0 4 * * *",
        llm_runtime=None,
        config=build_startup_config(valid_env(DATABASE_URL=postgres_url)),
    )

    output = runtime.read_diagnostics("endpoint", str(endpoint["id"]))

    assert "rejection=quality_gate:below_gate" in output


@pytest.mark.spec("runtime-bootstrap::Production dispatch executes a real stage")
def test_canonical_stage_list_matches_pipeline_order():
    stages = build_canonical_stages(metadata_sync=lambda **_kwargs: None)

    assert [stage.name for stage in stages] == CANONICAL_STAGE_NAMES


@pytest.mark.spec("runtime-bootstrap::Production dispatch executes a real stage")
def test_composed_runner_surfaces_stage_failure(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    config = build_startup_config(valid_env(DATABASE_URL=postgres_url))
    runtime = compose_runtime(config, metadata_sync=lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")))

    result = runtime.run_command("sync-metadata", object())

    assert result.exit_code == 4
    assert result.error_reason == "boom"


@pytest.mark.spec("runtime-bootstrap::Production dispatch executes a real stage")
def test_production_sync_metadata_uses_composed_stage(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    config = build_startup_config(valid_env(DATABASE_URL=postgres_url))
    calls = []
    result = MetadataSyncResult(candidates={}, aa_snapshot=AASnapshot(index_version="4.1", models=()))

    def metadata_sync(**kwargs):
        calls.append(kwargs)
        return result

    runtime = compose_runtime(config, metadata_sync=metadata_sync)

    result = runtime.run_command("sync-metadata", object())

    assert result.exit_code == 0
    assert calls == [{"dry_run": False}]


@pytest.mark.spec("llm-runtime::Client built from config")
@pytest.mark.spec("llm-runtime::No site bypasses the shared runtime")
@pytest.mark.spec("llm-runtime::Bootstrap model used before any catalog match")
def test_production_llm_runtime_uses_instructor_from_openai_and_bootstrap_model(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    config = build_startup_config(
        valid_env(
            DATABASE_URL=postgres_url,
            LLM_BOOTSTRAP_MODEL_ID="provider-bootstrap:conn-bootstrap",
            LLM_BOOTSTRAP_MODEL_CONFIRMED_FREE="true",
        )
    )
    client = PipelineOpsClient()
    client.quota_body["providers"] = [
        {
            "provider": "provider-bootstrap",
            "connectionId": "conn-bootstrap",
            "quotaTotal": 100,
            "quotaUsed": 20,
            "quotaWindow": "day",
            "percentRemaining": 80,
            "resetAt": None,
        }
    ]
    openai_clients = []
    instructor_clients = []
    fake_instructor_client = FakeInstructorClient()

    def openai_client_factory(**kwargs):
        client = FakeOpenAIClient(**kwargs)
        openai_clients.append(client)
        return client

    def instructor_from_openai(client):
        instructor_clients.append(client)
        return fake_instructor_client

    runtime = build_production_llm_runtime(
        config,
        repository,
        live_quota_client=client,
        adapters=StageAdapters(
            instructor_from_openai=instructor_from_openai,
            openai_client_factory=openai_client_factory,
        ),
    )

    response = runtime.complete(
        site=type(
            "Site",
            (),
            {
                "name": "quota-research-inspector",
                "model": "paid-static",
                "prompt_path": None,
                "max_prompt_chars": 1000,
                "retries": 1,
            },
        )(),
        context={"prompt": "quota"},
        response_model=QuotaClaimResponse,
    )

    assert response.amount == 1
    assert openai_clients[0].kwargs == {"base_url": "https://omniroute.test/v1", "api_key": "test-key"}
    assert instructor_clients == openai_clients
    assert fake_instructor_client.chat.completions.calls[0]["model"] == "provider-bootstrap:conn-bootstrap"


@pytest.mark.spec("llm-runtime::Highest-index confirmed-free model selected")
@pytest.mark.spec("llm-runtime::Falls to next model by index on unavailability")
def test_llm_model_selection_uses_confirmed_free_index_order_and_no_llm_fallback(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    config = build_startup_config(valid_env(DATABASE_URL=postgres_url))
    seed_confirmed_llm_candidate(
        repository,
        model_id="free-low",
        intelligence_index=40,
        connection_id="conn-provider-a",
    )
    seed_confirmed_llm_candidate(
        repository, model_id="free-high", intelligence_index=90, remaining=0, connection_id="conn-provider-a"
    )
    seed_confirmed_llm_candidate(
        repository,
        model_id="free-unhealthy",
        intelligence_index=95,
        health_status="degraded",
        connection_id="conn-provider-a",
    )

    client = PipelineOpsClient()
    selected = select_llm_model(repository, config, client)

    with repository.database.transaction() as transaction:
        combo_count = transaction.execute("SELECT count(*) AS total FROM combo_snapshots").fetchone()["total"]
    assert selected == "free-low"
    assert combo_count == 0

    assert select_llm_model(repository, config) is None


@pytest.mark.spec("llm-runtime::Falls to next model by index on unavailability")
@pytest.mark.spec("llm-runtime::Just-consumed quota is not selected")
def test_llm_model_selection_requires_fresh_live_quota_before_returning_candidate(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    config = build_startup_config(valid_env(DATABASE_URL=postgres_url))
    seed_confirmed_llm_candidate(
        repository,
        model_id="free-low-percent",
        intelligence_index=100,
        provider_id="provider-low-percent",
        connection_id="conn-low-percent",
    )
    seed_confirmed_llm_candidate(
        repository,
        model_id="free-locked",
        intelligence_index=90,
        provider_id="provider-locked",
        connection_id="conn-locked",
    )
    seed_confirmed_llm_candidate(
        repository,
        model_id="free-exhausted",
        intelligence_index=80,
        provider_id="provider-exhausted",
        connection_id="conn-exhausted",
    )
    seed_confirmed_llm_candidate(
        repository,
        model_id="free-usable",
        intelligence_index=70,
        provider_id="provider-usable",
        connection_id="conn-usable",
    )
    client = PipelineOpsClient()
    client.quota_body["providers"] = [
        {
            "provider": "provider-low-percent",
            "connectionId": "conn-low-percent",
            "quotaTotal": 100,
            "quotaUsed": 89,
            "quotaWindow": "day",
            "percentRemaining": 10,
            "resetAt": None,
        },
        {
            "provider": "provider-locked",
            "connectionId": "conn-locked",
            "quotaTotal": 100,
            "quotaUsed": 20,
            "quotaWindow": "day",
            "percentRemaining": 80,
            "resetAt": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        },
        {
            "provider": "provider-exhausted",
            "connectionId": "conn-exhausted",
            "quotaTotal": 100,
            "quotaUsed": 100,
            "quotaWindow": "day",
            "percentRemaining": 50,
            "resetAt": None,
        },
        {
            "provider": "provider-usable",
            "connectionId": "conn-usable",
            "quotaTotal": 100,
            "quotaUsed": 20,
            "quotaWindow": "day",
            "percentRemaining": 80,
            "resetAt": None,
        },
    ]

    assert select_llm_model(repository, config, client) == "free-usable"
    assert client.get_calls[-1] == "/api/usage/quota"


@pytest.mark.spec("llm-runtime::No confirmed-free model degrades to no-LLM")
def test_llm_model_selection_returns_none_without_catalog_or_bootstrap(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    config = build_startup_config(valid_env(DATABASE_URL=postgres_url))

    assert select_llm_model(repository, config) is None


@pytest.mark.spec("aa-index-migration::Advisory proposal generated")
@pytest.mark.spec("aa-index-migration::Deterministic approval and rollout")
def test_aa_index_runtime_generates_approves_rolls_out_and_rolls_back(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    seed_confirmed_llm_candidate(repository, model_id="free-migration", intelligence_index=88)
    with repository.database.transaction() as transaction:
        transaction.execute("UPDATE artificial_analysis_model_metrics SET index_version = '4.2'")
        repository.roles.upsert(
            transaction,
            role_id="routing_fast",
            requirements={"capabilities": []},
            expected_load={"requests": 1},
            criticality=1,
        )
    config = build_startup_config(valid_env(DATABASE_URL=postgres_url))
    fake_instructor_client = FakeInstructorClient()
    runtime = compose_runtime(
        config,
        adapters=StageAdapters(
            instructor_from_openai=lambda _client: fake_instructor_client,
            openai_client_factory=lambda **kwargs: FakeOpenAIClient(**kwargs),
            hermes_inventory=lambda _config: hermes_inventory_fixture(),
        ),
    )

    proposal = runtime.run_aa_index("analyze", object())
    approved = runtime.run_aa_index("approve", object())
    rolled_out = runtime.run_aa_index("rollout", object())
    rolled_back = runtime.run_aa_index("rollback", object())

    with repository.database.transaction() as transaction:
        migration = transaction.execute(
            "SELECT status, threshold_proposal_json FROM artificial_analysis_index_migrations"
        ).fetchone()
        threshold = transaction.execute(
            "SELECT role_id, metric, threshold_value, is_active FROM artificial_analysis_threshold_versions"
        ).fetchone()
    assert proposal.exit_code == 0
    assert approved.exit_code == 0
    assert rolled_out.exit_code == 0
    assert rolled_back.exit_code == 0
    assert fake_instructor_client.chat.completions.calls[0]["model"] == "free-migration"
    assert migration["status"] == "rolled_back"
    assert migration["threshold_proposal_json"]["roles"]["routing_fast"]["threshold"] == 60
    assert threshold["role_id"] == "routing_fast"
    assert threshold["metric"] == "intelligence_index"
    assert float(threshold["threshold_value"]) == 60.0
    assert threshold["is_active"] is False


@pytest.mark.spec("aa-index-migration::AA unavailable freezes thresholds")
@pytest.mark.spec("cli-and-operations::aa-index failure maps to an exit code")
def test_aa_index_analyze_fails_closed_without_aa_snapshot_or_model(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    config = build_startup_config(valid_env(DATABASE_URL=postgres_url))
    runtime = compose_runtime(
        config,
        adapters=StageAdapters(
            instructor_from_openai=lambda _client: FakeInstructorClient(),
            openai_client_factory=lambda **kwargs: FakeOpenAIClient(**kwargs),
            hermes_inventory=lambda _config: hermes_inventory_fixture(),
        ),
    )

    result = runtime.run_aa_index("analyze", object())

    with runtime.repository.database.transaction() as transaction:
        migration_count = transaction.execute(
            "SELECT count(*) AS total FROM artificial_analysis_index_migrations"
        ).fetchone()["total"]
        combo_count = transaction.execute(
            "SELECT count(*) AS total FROM combo_snapshots WHERE omniroute_combo_id LIKE 'fmo-%'"
        ).fetchone()["total"]
    assert result.exit_code == 4
    assert result.error_reason == "aa_unavailable"
    assert migration_count == 0
    assert combo_count == 0


@pytest.mark.spec("persistence::Sync writes metadata through the repository")
def test_sync_metadata_stage_persists_candidates_and_aa_snapshot(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    config = build_startup_config(valid_env(DATABASE_URL=postgres_url))
    result = MetadataSyncResult(
        candidates={
            ("models-dev", "free-chat"): FreeCandidate(
                provider_id="models-dev",
                model_id="free-chat",
                display_name="Free Chat",
                reasons=("zero_cost",),
            )
        },
        aa_snapshot=AASnapshot(
            index_version="4.1",
            models=(
                AAModelMetrics(
                    model_id="free-chat",
                    metrics={"intelligence_index": 71, "median_output_tokens_per_second": 34},
                    available=True,
                ),
            ),
        ),
    )
    runtime = compose_runtime(config, metadata_sync=lambda **_kwargs: result, adapters=empty_stage_adapters())

    cli_result = runtime.run_command("sync-metadata", object())

    repository = Repository(Database(postgres_url))
    with repository.database.transaction() as transaction:
        stored = transaction.execute("SELECT provider_id, provider_model_id FROM free_model_definitions").fetchall()
        quality = transaction.execute(
            """
            SELECT provider_id, provider_model_id, category, normalized_score
            FROM free_provider_quality_observations
            ORDER BY category
            """
        ).fetchall()
    assert cli_result.exit_code == 0
    assert [(row["provider_id"], row["provider_model_id"]) for row in stored] == [("models-dev", "free-chat")]
    assert [(row["category"], float(row["normalized_score"])) for row in quality] == [
        ("intelligence_index", 71.0),
        ("median_output_tokens_per_second", 34.0),
    ]


@pytest.mark.spec("persistence::Dry-run persists nothing")
def test_sync_metadata_stage_dry_run_persists_nothing(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    config = build_startup_config(valid_env(DATABASE_URL=postgres_url))
    result = MetadataSyncResult(
        candidates={
            ("models-dev", "free-chat"): FreeCandidate(
                provider_id="models-dev",
                model_id="free-chat",
                reasons=("zero_cost",),
            )
        },
        aa_snapshot=AASnapshot(index_version="4.1", models=()),
        dry_run=True,
    )
    args = type("Args", (), {"dry_run": True})()
    runtime = compose_runtime(config, metadata_sync=lambda **_kwargs: result, adapters=empty_stage_adapters())

    cli_result = runtime.run_command("sync-metadata", args)

    repository = Repository(Database(postgres_url))
    with repository.database.transaction() as transaction:
        count = transaction.execute("SELECT count(*) AS total FROM free_model_definitions").fetchone()["total"]
    assert cli_result.exit_code == 0
    assert count == 0


@pytest.mark.spec("scheduler::External metadata before discovery and scoring")
def test_full_pipeline_persists_metadata_before_downstream_stages(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    config = build_startup_config(valid_env(DATABASE_URL=postgres_url))
    result = MetadataSyncResult(
        candidates={
            ("models-dev", "free-chat"): FreeCandidate(
                provider_id="models-dev",
                model_id="free-chat",
                reasons=("zero_cost",),
            )
        },
        aa_snapshot=AASnapshot(index_version="4.1", models=()),
    )
    runtime = compose_runtime(
        config,
        metadata_sync=lambda **_kwargs: result,
        adapters=empty_adapters_with_stage_effects(),
    )

    cli_result = runtime.run_command("full", object())

    repository = Repository(Database(postgres_url))
    with repository.database.transaction() as transaction:
        run = repository.runs.list(transaction)[0]
        count = transaction.execute("SELECT count(*) AS total FROM free_model_definitions").fetchone()["total"]
    stage_names = [stage["name"] for stage in run["error_json"]["stages"]]
    assert cli_result.exit_code == 0
    assert count == 1
    assert stage_names.index("external-metadata-sync") < stage_names.index("free-candidate-discovery")
    assert stage_names.index("external-metadata-sync") < stage_names.index("role-scoring")


@pytest.mark.spec("scheduler::Service fires the daily run")
def test_composed_scheduler_run_once_starts_full_pipeline_at_cron(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    config = build_startup_config(valid_env(DATABASE_URL=postgres_url, HERMES_INVENTORY_CRON="0 4 * * *"))
    result = MetadataSyncResult(candidates={}, aa_snapshot=AASnapshot(index_version="4.1", models=()))
    runtime = compose_runtime(
        config,
        metadata_sync=lambda **_kwargs: result,
        adapters=empty_adapters_with_stage_effects(),
    )

    cron_now = datetime.now(UTC).replace(hour=4, minute=0, second=0, microsecond=0)
    cli_result = runtime.run_scheduler_once(cron_now.isoformat())

    repository = Repository(Database(postgres_url))
    with repository.database.transaction() as transaction:
        runs = [run for run in repository.runs.list(transaction) if run["run_type"] == "full"]
    assert cli_result.exit_code == 0
    assert len(runs) == 1
    assert runs[0]["trigger"] == "scheduled"
    assert runs[0]["run_type"] == "full"


@pytest.mark.spec("pipeline-orchestration::Full run calls production adapters")
def test_full_runtime_invokes_every_production_adapter_in_order(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    config = build_startup_config(valid_env(DATABASE_URL=postgres_url))
    calls = []

    def metadata_sync(**_kwargs):
        calls.append("external-metadata-sync")
        return MetadataSyncResult(candidates={}, aa_snapshot=AASnapshot(index_version="4.1", models=()))

    def registry_sync(_client):
        calls.append("free-candidate-discovery:registry")
        return FreeRegistrySyncOutcome(
            registry=FreeRegistry(models={}, pool_budgets={}),
            free_models_payload={"models": []},
            rankings_payload={"providers": []},
            model_count=0,
            drift=[],
            errors=[],
        )

    def catalog_scan(_scanner, _client, _omniroute_instance_id):
        calls.append("free-candidate-discovery:catalog")
        return {}

    def domain_stage(name):
        def run(_dependencies, _context):
            calls.append(name)
            return effectful_success(name, "idempotent_no_change")

        return run

    runtime = compose_runtime(
        config,
        metadata_sync=metadata_sync,
        adapters=StageAdapters(
            registry_sync=registry_sync,
            catalog_scan=catalog_scan,
            account_discovery=empty_stage_adapters().account_discovery,
            stage_adapters={name: domain_stage(name) for name in CANONICAL_STAGE_NAMES[2:]},
        ),
    )

    result = runtime.run_command("full", object())

    assert result.exit_code == 0
    assert calls == [
        "external-metadata-sync",
        "free-candidate-discovery:registry",
        "free-candidate-discovery:catalog",
        "model-matching",
        "quota-research",
        "access-classification",
        "probing",
        "telemetry-sync",
        "quota-sync",
        "hermes-inventory",
        "role-lifecycle",
        "role-scoring",
        "demand-forecast",
        "allocation",
        "diff",
        "apply",
        "audit",
    ]
    repository = Repository(Database(postgres_url))
    with repository.database.transaction() as transaction:
        run = repository.runs.list(transaction)[0]
    for record in run["error_json"]["stages"][2:]:
        assert_success_has_declared_effect(record)


@pytest.mark.spec("runtime-bootstrap::Placeholder stage rejected")
@pytest.mark.spec("pipeline-orchestration::Full run calls production adapters")
def test_production_composition_has_no_success_placeholder_helper():
    source = Path("src/fmo/composition.py").read_text(encoding="utf-8")
    stages = build_canonical_stages(metadata_sync=lambda **_kwargs: None)

    assert "_successful_stage" not in source
    assert "_domain_stage_adapter" not in source
    assert "domain_stage" not in source
    assert [stage.name for stage in stages] == CANONICAL_STAGE_NAMES


@pytest.mark.spec("pipeline-orchestration::Unwired stage fails closed")
def test_unwired_canonical_stage_returns_not_implemented_and_stops_full(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    config = build_startup_config(valid_env(DATABASE_URL=postgres_url))
    result = MetadataSyncResult(candidates={}, aa_snapshot=AASnapshot(index_version="4.1", models=()))
    runtime = compose_runtime(config, metadata_sync=lambda **_kwargs: result, adapters=empty_stage_adapters())

    cli_result = runtime.run_command("full", object())

    repository = Repository(Database(postgres_url))
    with repository.database.transaction() as transaction:
        run = repository.runs.list(transaction)[0]
    stages = run["error_json"]["stages"]
    assert cli_result.exit_code == 3
    assert [stage["name"] for stage in stages] == [
        "external-metadata-sync",
        "free-candidate-discovery",
        "account-discovery",
        "model-matching",
    ]
    assert stages[-1]["status"] == "not_implemented"
    assert stages[-1]["reason"] == "model-matching adapter is not wired"
