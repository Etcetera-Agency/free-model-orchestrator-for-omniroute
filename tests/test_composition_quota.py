from __future__ import annotations

import pytest

from tests._composition_support import (
    UTC,
    Database,
    MigrationRunner,
    PartiallyFailingQuotaSearchClient,
    Path,
    PipelineOpsClient,
    QuotaSearchClient,
    RecordingLlmRuntime,
    Repository,
    StageDependencies,
    datetime,
    run_composed_stage,
    run_composed_stage_with_dependencies,
    run_runtime_command,
    seed_endpoint,
    seed_free_registry_snapshot,
    timedelta,
)


@pytest.mark.spec("pipeline-orchestration::Quota research persists capped rules")
@pytest.mark.spec("quota-research::Inspector path taken when runtime available")
@pytest.mark.spec("quota-research::Inspector cannot exceed the deterministic cap")
def test_quota_research_stage_persists_snapshot_and_capped_rule(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    seed_endpoint(repository)
    run_composed_stage(repository, "model-matching")
    client = QuotaSearchClient()
    llm_runtime = RecordingLlmRuntime(quota_amount=200.0)
    dependencies = StageDependencies(repository=repository, omniroute_client=client, llm_runtime=llm_runtime)

    result = run_composed_stage_with_dependencies(repository, "quota-research", dependencies)

    with repository.database.transaction() as transaction:
        snapshot_count = transaction.execute("SELECT count(*) AS total FROM quota_source_snapshots").fetchone()["total"]
        rule = transaction.execute("SELECT confidence, limits FROM quota_rules").fetchone()
    assert result.exit_code == 0
    assert result.stage_results[0]["details"]["effect"] == "repository_write"
    assert client.calls[0][0] == "/v1/search"
    assert llm_runtime.calls[0]["site"] == "quota-research-inspector"
    assert snapshot_count == 1
    assert float(rule["confidence"]) == 0.70
    assert rule["limits"]["requests"] == 200.0


@pytest.mark.spec("quota-research::Fails open to deterministic extraction")
def test_quota_research_falls_back_to_summary_extraction_when_inspector_fails(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    seed_endpoint(repository)
    run_composed_stage(repository, "model-matching")
    client = QuotaSearchClient()
    llm_runtime = RecordingLlmRuntime(fail=True)
    dependencies = StageDependencies(repository=repository, omniroute_client=client, llm_runtime=llm_runtime)

    result = run_composed_stage_with_dependencies(repository, "quota-research", dependencies)

    with repository.database.transaction() as transaction:
        rule = transaction.execute("SELECT confidence, limits FROM quota_rules").fetchone()
    assert result.exit_code == 0
    assert llm_runtime.calls[0]["site"] == "quota-research-inspector"
    assert float(rule["confidence"]) == 0.70
    assert rule["limits"]["requests"] == 100.0


@pytest.mark.spec("pipeline-orchestration::Access classification persists status")
def test_access_classification_stage_persists_canonical_status_and_evidence(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    endpoint = seed_endpoint(repository)
    run_composed_stage(repository, "model-matching")
    run_composed_stage(repository, "quota-research")

    result = run_composed_stage(repository, "access-classification")

    with repository.database.transaction() as transaction:
        access = transaction.execute(
            "SELECT status, evidence FROM endpoint_access_states WHERE endpoint_id = %(endpoint_id)s",
            {"endpoint_id": endpoint["id"]},
        ).fetchone()
        attribution = transaction.execute(
            "SELECT attribution_status, evidence_json FROM endpoint_quota_attribution WHERE endpoint_id = %(endpoint_id)s",
            {"endpoint_id": endpoint["id"]},
        ).fetchone()
        stored = repository.provider_endpoints.get(transaction, endpoint["id"])
    assert result.exit_code == 0
    assert result.stage_results[0]["details"]["effect"] == "repository_write"
    assert access["status"] == "confirmed"
    assert access["evidence"]["free_access"] is True
    assert attribution["attribution_status"] == "confirmed"
    assert stored["access_status"] == "confirmed"


@pytest.mark.spec("access-classifier::Missing endpoint-local quota evidence fails closed")
def test_access_classification_records_missing_quota_without_aborting_other_endpoints(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    confirmed_endpoint = seed_endpoint(repository, model_id="with-rule")
    seed_endpoint(repository, model_id="missing-rule")
    run_composed_stage(repository, "model-matching")
    with repository.database.transaction() as transaction:
        row = transaction.execute(
            """
            SELECT p.id AS provider_id, pa.id AS account_id
            FROM provider_endpoints pe
            JOIN provider_accounts pa ON pa.id = pe.provider_account_id
            JOIN providers p ON p.id = pa.provider_id
            WHERE pe.id = %(endpoint_id)s
            """,
            {"endpoint_id": confirmed_endpoint["id"]},
        ).fetchone()
        repository.quota_rules.upsert(
            transaction,
            provider_id=row["provider_id"],
            provider_account_id=row["account_id"],
            source_snapshot_id=None,
            model_pattern="with-rule",
            access_type="free_quota",
            limits={"requests": 100, "window": "day"},
            reset_policy={"window": "day"},
            hard_stop_capable=True,
            confidence=0.7,
            status="active",
            rule_hash="with-rule:test",
        )

    result = run_composed_stage(repository, "access-classification")

    with repository.database.transaction() as transaction:
        states = transaction.execute(
            """
            SELECT pe.provider_model_id, pe.access_status, eas.status, eas.reason_code, eas.evidence
            FROM provider_endpoints pe
            JOIN endpoint_access_states eas ON eas.endpoint_id = pe.id
            ORDER BY pe.provider_model_id
            """
        ).fetchall()
    assert result.exit_code == 0
    assert [(row["provider_model_id"], row["status"], row["reason_code"]) for row in states] == [
        ("missing-rule", "unknown", "quota_rule_missing"),
        ("with-rule", "confirmed", "quota_rule_remaining"),
    ]
    assert [row["access_status"] for row in states] == ["unknown", "confirmed"]
    assert states[0]["evidence"]["free_access"] is False


@pytest.mark.spec("pipeline-orchestration::External payload missing fails closed")
def test_quota_research_missing_external_payload_fails_closed(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    seed_endpoint(repository)
    run_composed_stage(repository, "model-matching")

    result = run_composed_stage(repository, "quota-research", client=QuotaSearchClient(answer="No quota found."))

    assert result.exit_code == 4
    assert result.status == "external_dependency_failed"
    assert result.stage_results[0]["reason"] == "missing_amount"


@pytest.mark.spec("quota-research::No new free model skips quota research")
@pytest.mark.spec("pipeline-orchestration::No new free model leaves quota research skipped")
def test_quota_research_skips_when_free_registry_snapshot_is_unchanged(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    seed_endpoint(repository)
    run_composed_stage(repository, "model-matching")
    now = datetime.now(UTC)
    seed_free_registry_snapshot(repository, models=[("provider-a", "free-chat")], created_at=now - timedelta(days=1))
    seed_free_registry_snapshot(repository, models=[("provider-a", "free-chat")], created_at=now)
    client = PipelineOpsClient()

    result = run_composed_stage(repository, "quota-research", client=client)

    assert result.exit_code == 0
    assert result.stage_results[0]["details"]["effect"] == "idempotent_no_change"
    assert result.stage_results[0]["details"]["reason"] == "no_free_model_change"
    assert not [call for call in client.calls if call[0] == "/v1/search"]


@pytest.mark.spec("quota-research::Provider account recalc researches one quota pool")
@pytest.mark.spec("pipeline-orchestration::Quota research is triggered by new free models")
def test_new_reachable_free_model_triggers_provider_account_recalc_and_uses_quota_total_hint(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    seed_endpoint(repository, model_id="free-chat")
    seed_endpoint(repository, model_id="new-free")
    run_composed_stage(repository, "model-matching")
    now = datetime.now(UTC)
    seed_free_registry_snapshot(repository, models=[("provider-a", "free-chat")], created_at=now - timedelta(days=1))
    seed_free_registry_snapshot(
        repository,
        models=[("provider-a", "free-chat"), ("provider-a", "new-free")],
        created_at=now,
    )
    client = PipelineOpsClient()
    llm_runtime = RecordingLlmRuntime(quota_amount=50.0)
    dependencies = StageDependencies(repository=repository, omniroute_client=client, llm_runtime=llm_runtime)

    result = run_composed_stage_with_dependencies(repository, "quota-research", dependencies)

    with repository.database.transaction() as transaction:
        rule_rows = transaction.execute("SELECT limits FROM quota_rules ORDER BY model_pattern").fetchall()
    assert result.exit_code == 0
    assert [call[0] for call in client.calls if call[0] == "/v1/search"] == ["/v1/search"]
    assert [row["limits"]["requests"] for row in rule_rows] == [50.0]


@pytest.mark.spec("quota-research::Endpoint filter researches one endpoint")
def test_quota_research_endpoint_filter_limits_research_to_one_endpoint(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    seed_endpoint(repository, model_id="selected-free")
    seed_endpoint(repository, model_id="skipped-free")
    run_composed_stage(repository, "model-matching")
    now = datetime.now(UTC)
    seed_free_registry_snapshot(
        repository, models=[("provider-a", "selected-free")], created_at=now - timedelta(days=1)
    )
    seed_free_registry_snapshot(
        repository,
        models=[("provider-a", "selected-free"), ("provider-a", "skipped-free")],
        created_at=now,
    )
    client = PipelineOpsClient()

    result = run_runtime_command(repository, client, "research-quotas", endpoint="selected-free")

    with repository.database.transaction() as transaction:
        rules = transaction.execute("SELECT model_pattern FROM quota_rules ORDER BY model_pattern").fetchall()
    assert result.exit_code == 0
    assert len([call for call in client.calls if call[0] == "/v1/search"]) == 1
    assert "selected-free" in client.calls[0][1]["query"]
    assert "skipped-free" not in client.calls[0][1]["query"]
    assert [row["model_pattern"] for row in rules] == ["selected-free"]


@pytest.mark.spec("access-classifier::Provider account wildcard quota rule applies to endpoint")
def test_access_classification_uses_provider_account_wildcard_quota_rule(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    first_endpoint = seed_endpoint(repository, model_id="first-free")
    second_endpoint = seed_endpoint(repository, model_id="second-free")
    run_composed_stage(repository, "model-matching")
    with repository.database.transaction() as transaction:
        row = transaction.execute(
            """
            SELECT p.id AS provider_id, pa.id AS account_id
            FROM provider_endpoints pe
            JOIN provider_accounts pa ON pa.id = pe.provider_account_id
            JOIN providers p ON p.id = pa.provider_id
            WHERE pe.id = %(endpoint_id)s
            """,
            {"endpoint_id": first_endpoint["id"]},
        ).fetchone()
        repository.quota_rules.upsert(
            transaction,
            provider_id=row["provider_id"],
            provider_account_id=row["account_id"],
            source_snapshot_id=None,
            model_pattern="*",
            access_type="free_quota",
            limits={"requests": 100, "window": "day"},
            reset_policy={"window": "day"},
            hard_stop_capable=True,
            confidence=0.7,
            status="active",
            rule_hash="provider-account:test",
        )

    result = run_composed_stage(repository, "access-classification")

    with repository.database.transaction() as transaction:
        states = transaction.execute(
            """
            SELECT pe.provider_model_id, eas.status, eas.reason_code
            FROM provider_endpoints pe
            JOIN endpoint_access_states eas ON eas.endpoint_id = pe.id
            WHERE pe.id IN (%(first_endpoint)s, %(second_endpoint)s)
            ORDER BY pe.provider_model_id
            """,
            {"first_endpoint": first_endpoint["id"], "second_endpoint": second_endpoint["id"]},
        ).fetchall()
    assert result.exit_code == 0
    assert [(row["provider_model_id"], row["status"], row["reason_code"]) for row in states] == [
        ("first-free", "confirmed", "quota_rule_remaining"),
        ("second-free", "confirmed", "quota_rule_remaining"),
    ]


@pytest.mark.spec("quota-research::One endpoint error does not stop research for the rest")
@pytest.mark.spec("quota-research::Per-endpoint failures mark the run partial")
def test_quota_research_continues_after_one_endpoint_error(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    for model_id in ["good-free", "bad-free", "later-free"]:
        seed_endpoint(
            repository,
            model_id=model_id,
            provider_id=f"{model_id}-provider",
            connection_id=f"{model_id}-connection",
        )
    run_composed_stage(repository, "model-matching")
    now = datetime.now(UTC)
    seed_free_registry_snapshot(
        repository,
        models=[("good-free-provider", "good-free")],
        created_at=now - timedelta(days=1),
    )
    seed_free_registry_snapshot(
        repository,
        models=[
            ("good-free-provider", "good-free"),
            ("bad-free-provider", "bad-free"),
            ("later-free-provider", "later-free"),
        ],
        created_at=now,
    )
    client = PartiallyFailingQuotaSearchClient(failing_model="bad-free")

    result = run_composed_stage(repository, "quota-research", client=client)

    with repository.database.transaction() as transaction:
        rules = transaction.execute("SELECT model_pattern FROM quota_rules ORDER BY model_pattern").fetchall()
    assert result.exit_code == 2
    assert result.status == "partial_stale"
    assert client.attempted_models == ["bad-free", "good-free", "later-free"]
    assert [row["model_pattern"] for row in rules] == ["good-free", "later-free"]


@pytest.mark.spec("quota-research::New model outside our connections does not trigger")
def test_new_free_model_outside_our_connections_does_not_trigger_recalc(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    seed_endpoint(repository)
    run_composed_stage(repository, "model-matching")
    now = datetime.now(UTC)
    seed_free_registry_snapshot(repository, models=[("provider-a", "free-chat")], created_at=now - timedelta(days=1))
    seed_free_registry_snapshot(
        repository,
        models=[("provider-a", "free-chat"), ("provider-b", "outside-free")],
        created_at=now,
    )
    client = PipelineOpsClient()

    result = run_composed_stage(repository, "quota-research", client=client)

    assert result.exit_code == 0
    assert result.stage_results[0]["details"]["effect"] == "idempotent_no_change"
    assert not [call for call in client.calls if call[0] == "/v1/search"]


@pytest.mark.spec("quota-research::Changed free status triggers recalc")
def test_changed_free_status_triggers_recalc_and_deactivates_lost_free_rule(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    seed_endpoint(repository, model_id="lost-free")
    run_composed_stage(repository, "model-matching")
    now = datetime.now(UTC)
    seed_free_registry_snapshot(repository, models=[("provider-a", "lost-free")], created_at=now - timedelta(days=1))
    seed_free_registry_snapshot(repository, models=[], created_at=now)
    client = PipelineOpsClient()

    result = run_composed_stage(repository, "quota-research", client=client)

    with repository.database.transaction() as transaction:
        rule = transaction.execute("SELECT status FROM quota_rules WHERE model_pattern = 'lost-free'").fetchone()
        endpoint = transaction.execute(
            "SELECT access_status FROM provider_endpoints WHERE provider_model_id = 'lost-free'"
        ).fetchone()
        definition = transaction.execute(
            "SELECT status FROM free_model_definitions WHERE provider_model_id = 'lost-free'"
        ).fetchone()
    assert result.exit_code == 0
    assert [call[0] for call in client.calls if call[0] == "/v1/search"] == ["/v1/search"]
    assert rule["status"] == "inactive"
    assert endpoint["access_status"] == "rejected"
    assert definition["status"] == "inactive"
