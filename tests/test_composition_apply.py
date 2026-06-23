from __future__ import annotations

import pytest

from tests._composition_support import (
    OPENAI_CHAT_COMPLETION_BODY,
    ComboApplier,
    Database,
    MigrationRunner,
    MultiComboOpsClient,
    Path,
    PipelineOpsClient,
    RecordingLlmRuntime,
    Repository,
    StageDependencies,
    _cli_result,
    _smoke_combo,
    build_startup_config,
    prepare_scored_endpoint,
    run_composed_stage,
    run_composed_stage_with_dependencies,
    run_runtime_command,
    seed_apply_ready_diff,
    structured_combo_step,
    valid_env,
)


@pytest.mark.spec("demand-forecast::Demand comes from the forecast")
@pytest.mark.spec("demand-forecast::Cold start floor applied")
@pytest.mark.spec("demand-forecast::Reserve applied once")
def test_demand_forecast_persists_floor_and_one_time_reserve(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    with repository.database.transaction() as transaction:
        repository.roles.upsert(
            transaction,
            role_id="cold",
            requirements={"capabilities": []},
            expected_load={"requests": 0},
            criticality=1,
        )
        transaction.execute("UPDATE roles SET role_lifecycle_status = 'bootstrap_pending' WHERE id = 'cold'")

    first = run_composed_stage(repository, "demand-forecast")
    second = run_composed_stage(repository, "demand-forecast")

    with repository.database.transaction() as transaction:
        forecasts = transaction.execute(
            """
            SELECT expected_requests, demand_source, base_historical_requests
            FROM role_demand_forecasts
            WHERE role_id = 'cold'
            ORDER BY created_at
            """
        ).fetchall()
    assert first.exit_code == 0
    assert second.exit_code == 0
    assert float(forecasts[0]["expected_requests"]) == 1.2
    assert forecasts[0]["demand_source"] == "bootstrap"
    assert float(forecasts[1]["expected_requests"]) == 1.0


@pytest.mark.spec("pipeline-orchestration::Allocation persists one combo plan per role")
@pytest.mark.spec("pipeline-orchestration::Oversubscription gate blocks zero-capacity pool")
@pytest.mark.spec("pipeline-orchestration::Inventory precedes scoring")
@pytest.mark.spec("allocator::Allocation target carries structured member identity")
@pytest.mark.spec("allocator::Family concentration reported")
def test_allocation_stage_persists_plan_and_constraint_report(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    client = PipelineOpsClient()
    prepare_scored_endpoint(repository, client=client)
    run_composed_stage(repository, "role-scoring", client=client)
    with repository.database.transaction() as transaction:
        repository.role_consumers.upsert(
            transaction,
            role_id="routing_fast",
            consumer_type="cron_job",
            consumer_key="demand-source",
            cadence="0 4 * * *",
            calls_per_run=33,
            source_hash="test",
        )
    run_composed_stage(repository, "demand-forecast", client=client)

    result = run_composed_stage(repository, "allocation", client=client)

    with repository.database.transaction() as transaction:
        plan = transaction.execute(
            "SELECT role_id, status, targets, constraint_report FROM allocation_plans"
        ).fetchone()
    assert result.exit_code == 0
    assert result.stage_results[0]["details"]["effect"] == "repository_write"
    assert plan["role_id"] == "routing_fast"
    assert plan["status"] == "planned"
    assert len(plan["targets"]) == 1
    target = plan["targets"][0]
    assert target["endpoint_id"]
    assert target["combo_step"] == {
        "kind": "model",
        "model": "free-chat",
        "providerId": "provider-a",
        "connectionId": "conn-provider-a",
        "weight": 0,
    }
    assert target["groups"]["provider_account_id"]
    assert target["groups"]["quota_pool_id"]
    assert target["groups"]["canonical_model_id"]
    assert "canonical_family" in target["groups"]
    assert target["score"] > 0
    assert plan["constraint_report"]["apply"] is True
    assert "canonical_family_concentration" in plan["constraint_report"]["diversity"]
    assert plan["constraint_report"]["pool_reports"][next(iter(plan["constraint_report"]["pool_reports"]))][
        "usage"
    ] == pytest.approx(39.6)


@pytest.mark.spec("pipeline-orchestration::Diff is computed without mutating OmniRoute")
@pytest.mark.spec("smart-combo-reviewer::Reviewer output is recorded")
@pytest.mark.spec("smart-combo-reviewer::Applied diff is independent of the reviewer")
@pytest.mark.spec("combo-applier::Endpoint ids retained for audit")
def test_diff_stage_persists_minimal_diff_without_mutating_omniroute(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    client = PipelineOpsClient()
    prepare_scored_endpoint(repository, client=client)
    run_composed_stage(repository, "role-scoring", client=client)
    run_composed_stage(repository, "demand-forecast", client=client)
    run_composed_stage(repository, "allocation", client=client)
    llm_runtime = RecordingLlmRuntime(
        review_diffs=[{"op": "add", "role": "routing_fast", "endpoint_id": "reviewer-added"}]
    )
    dependencies = StageDependencies(repository=repository, omniroute_client=client, llm_runtime=llm_runtime)

    result = run_composed_stage_with_dependencies(repository, "diff", dependencies)

    with repository.database.transaction() as transaction:
        snapshot = transaction.execute("SELECT phase, state_json FROM combo_snapshots").fetchone()
    assert result.exit_code == 0
    assert result.stage_results[0]["details"]["effect"] == "repository_write"
    assert client.get_calls[-1] == "/api/combos"
    assert not any(call[0].startswith("/api/combos") for call in client.calls)
    assert llm_runtime.calls[0]["site"] == "smart-combo-reviewer"
    assert snapshot["phase"] == "diff"
    assert snapshot["state_json"]["remove"] == ["old-endpoint"]
    assert snapshot["state_json"]["before"] == ["old-endpoint"]
    assert snapshot["state_json"]["before_endpoint_ids"] == ["old-endpoint"]
    assert snapshot["state_json"]["after_endpoint_ids"]
    assert snapshot["state_json"]["after"][0]["providerId"] == "provider-a"
    assert snapshot["state_json"]["after"][0]["connectionId"] == "conn-provider-a"
    assert snapshot["state_json"]["after"] != ["reviewer-added"]
    assert snapshot["state_json"]["advisory_review"]["status"] == "ok"


@pytest.mark.spec("smart-combo-reviewer::Reviewer disabled by trigger")
def test_diff_stage_skips_reviewer_when_site_limit_disabled(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    client = PipelineOpsClient()
    prepare_scored_endpoint(repository, client=client)
    run_composed_stage(repository, "role-scoring", client=client)
    run_composed_stage(repository, "demand-forecast", client=client)
    run_composed_stage(repository, "allocation", client=client)
    config = build_startup_config(valid_env(DATABASE_URL=postgres_url, LLM_SMART_REVIEW_CALL_LIMIT="0"))
    llm_runtime = RecordingLlmRuntime(review_diffs=[{"op": "add", "role": "routing_fast", "endpoint_id": "x"}])
    dependencies = StageDependencies(
        repository=repository, omniroute_client=client, config=config, llm_runtime=llm_runtime
    )

    result = run_composed_stage_with_dependencies(repository, "diff", dependencies)

    with repository.database.transaction() as transaction:
        snapshot = transaction.execute("SELECT state_json FROM combo_snapshots").fetchone()
    assert result.exit_code == 0
    assert llm_runtime.calls == []
    assert snapshot["state_json"]["advisory_review"]["status"] == "skipped_trigger"


@pytest.mark.spec("combo-applier::Smoke pass derived from OpenAI-compatible body")
def test_smoke_combo_accepts_openai_chat_completion_without_body_status_code():
    client = PipelineOpsClient()

    assert _smoke_combo(client, "fmo-routing_fast") is True

    smoke_call = client.calls[-1]
    assert smoke_call[0] == "/v1/chat/completions"
    assert "status_code" not in OPENAI_CHAT_COMPLETION_BODY


@pytest.mark.spec("combo-applier::Empty completion is a smoke failure")
def test_smoke_combo_rejects_empty_openai_chat_completion():
    client = PipelineOpsClient(smoke_status=204)

    assert _smoke_combo(client, "fmo-routing_fast") is False


@pytest.mark.spec("combo-applier::Non-2xx smoke response is a smoke failure")
def test_smoke_combo_maps_non_2xx_response_to_failure():
    client = PipelineOpsClient(smoke_status=500)

    assert _smoke_combo(client, "fmo-routing_fast") is False


@pytest.mark.spec("pipeline-orchestration::Production apply runs the real smoke test")
@pytest.mark.spec("combo-applier::Production apply smoke-tests applied combos")
@pytest.mark.spec("combo-applier::Fabricated smoke signal rejected")
@pytest.mark.spec("combo-applier::Smoke pass derived from OpenAI-compatible body")
@pytest.mark.spec("combo-applier::Apply reads combos through management API bridge")
@pytest.mark.spec("combo-applier::Apply writes existing combos through management API bridge")
@pytest.mark.spec("combo-applier::Public combo projection is never used for management apply")
@pytest.mark.spec("combo-applier::Research budget with healthy liveness passes")
@pytest.mark.spec("combo-applier::Endpoint with null reset is not rejected")
@pytest.mark.spec("combo-applier::Structured combo steps applied")
@pytest.mark.spec("omniroute-client::Bridge denies combo test helper")
def test_apply_stage_mutates_fmo_combo_and_reports_real_smoke_signal(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    client = PipelineOpsClient()
    prepare_scored_endpoint(repository, client=client)
    run_composed_stage(repository, "role-scoring", client=client)
    run_composed_stage(repository, "demand-forecast", client=client)
    run_composed_stage(repository, "allocation", client=client)
    run_composed_stage(repository, "diff", client=client)

    result = run_composed_stage(repository, "apply", client=client)

    assert result.exit_code == 0
    assert result.stage_results[0]["details"]["combo_test_called"] is True
    assert _cli_result(result).combo_test_called is True
    assert "/api/combos" in client.get_calls
    assert any(call[0] == "/v1/chat/completions" for call in client.calls)
    assert not any(call[0] == "/api/combos/test" for call in client.calls)
    assert not any(call[0] == "/v1/combos" for call in client.calls)
    combo_put = next(call for call in client.calls if call[0].startswith("/api/combos/"))
    assert combo_put[1]["models"] == [structured_combo_step(model_id="free-chat", connection_id="conn-provider-a")]
    assert combo_put[3]
    assert client.combos["fmo-routing_fast"] != ["old-endpoint"]


@pytest.mark.spec("pipeline-orchestration::Failing guard blocks apply")
@pytest.mark.spec("cli-and-operations::Apply dry-run previews without mutating")
def test_apply_stage_guard_failure_blocks_mutation(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    client = PipelineOpsClient()

    result = run_composed_stage(repository, "apply", client=client)

    assert result.exit_code == 5
    assert client.combos["fmo-routing_fast"] == ["old-endpoint"]


@pytest.mark.spec("cli-and-operations::Apply dry-run previews without mutating")
def test_apply_stage_dry_run_reports_unsafe_without_mutating(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    client = PipelineOpsClient()

    result = run_runtime_command(repository, client, "apply", dry_run=True)

    assert result.exit_code == 5
    assert result.error_reason.startswith("apply preconditions failed:")
    assert client.combos["fmo-routing_fast"] == ["old-endpoint"]
    assert not any(call[0].startswith("/api/combos/") for call in client.calls)
    assert not any(call[0] == "/api/combos/test" for call in client.calls)


@pytest.mark.spec("cli-and-operations::Apply dry-run previews without mutating")
def test_apply_stage_dry_run_previews_valid_plan_without_combo_mutation(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    client = PipelineOpsClient()
    prepare_scored_endpoint(repository, client=client)
    run_composed_stage(repository, "role-scoring", client=client)
    run_composed_stage(repository, "demand-forecast", client=client)
    run_composed_stage(repository, "allocation", client=client)
    run_composed_stage(repository, "diff", client=client)
    client.calls.clear()

    result = run_runtime_command(repository, client, "apply", dry_run=True)

    assert result.exit_code == 0
    assert result.changed is False
    assert result.combo_test_called is False
    assert client.combos["fmo-routing_fast"] == ["old-endpoint"]
    assert not any(call[0].startswith("/api/combos/") for call in client.calls)
    assert not any(call[0] == "/api/combos/test" for call in client.calls)


@pytest.mark.spec("combo-applier::Failing quota evidence blocks the apply stage")
@pytest.mark.spec("combo-applier::Exhausted or locked-out endpoint is excluded")
@pytest.mark.spec("pipeline-orchestration::Apply still excludes stale evidence")
@pytest.mark.parametrize(
    "quota_update",
    [
        "UPDATE endpoint_access_states SET hard_stop_capable = false",
        "UPDATE endpoint_access_states SET evidence = evidence || '{\"percent_remaining\": 1}'::jsonb",
        "UPDATE endpoint_access_states SET reset_at = now() + interval '1 minute', evidence = evidence || '{\"locked_out\": true}'::jsonb",
        "UPDATE endpoint_access_states SET classified_at = now() - interval '2 days'",
        "DELETE FROM endpoint_access_states",
    ],
)
def test_apply_stage_blocks_mutation_without_current_quota_safety(postgres_url, quota_update):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    client = PipelineOpsClient()
    prepare_scored_endpoint(repository, client=client)
    run_composed_stage(repository, "role-scoring", client=client)
    run_composed_stage(repository, "demand-forecast", client=client)
    run_composed_stage(repository, "allocation", client=client)
    run_composed_stage(repository, "diff", client=client)
    with repository.database.transaction() as transaction:
        transaction.execute(quota_update)

    result = run_composed_stage(repository, "apply", client=client)

    assert result.exit_code == 5
    assert client.combos["fmo-routing_fast"] == ["old-endpoint"]
    assert not any(call[0].startswith("/api/combos/") for call in client.calls)


@pytest.mark.spec("combo-applier::Assumed remaining does not satisfy the apply gate")
def test_apply_stage_rejects_assumed_remaining_evidence(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    client = PipelineOpsClient()
    prepare_scored_endpoint(repository, client=client)
    run_composed_stage(repository, "role-scoring", client=client)
    run_composed_stage(repository, "demand-forecast", client=client)
    run_composed_stage(repository, "allocation", client=client)
    run_composed_stage(repository, "diff", client=client)
    with repository.database.transaction() as transaction:
        transaction.execute(
            """
            UPDATE endpoint_access_states
            SET evidence = '{"remaining_source": "assumed", "safety_buffer": 1}'::jsonb
            """
        )

    result = run_composed_stage(repository, "apply", client=client)

    assert result.exit_code == 5
    assert client.combos["fmo-routing_fast"] == ["old-endpoint"]
    assert not any(call[0].startswith("/api/combos/") for call in client.calls)


@pytest.mark.spec("combo-applier::Zero safety buffer does not satisfy the apply gate")
def test_apply_stage_uses_minimum_safety_buffer_floor(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    client = PipelineOpsClient()
    prepare_scored_endpoint(repository, client=client)
    run_composed_stage(repository, "role-scoring", client=client)
    run_composed_stage(repository, "demand-forecast", client=client)
    run_composed_stage(repository, "allocation", client=client)
    run_composed_stage(repository, "diff", client=client)
    with repository.database.transaction() as transaction:
        transaction.execute(
            """
            UPDATE endpoint_access_states
            SET effective_remaining = '{"requests": 1}'::jsonb,
                evidence = '{"remaining_source": "live_observed"}'::jsonb
            """
        )

    result = run_composed_stage(repository, "apply", client=client)

    assert result.exit_code == 5
    assert client.combos["fmo-routing_fast"] == ["old-endpoint"]
    assert not any(call[0].startswith("/api/combos/") for call in client.calls)


@pytest.mark.spec("combo-applier::Failing probe evidence blocks the apply stage")
def test_apply_stage_blocks_mutation_without_current_probe_success(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    client = PipelineOpsClient()
    prepare_scored_endpoint(repository, client=client)
    run_composed_stage(repository, "role-scoring", client=client)
    run_composed_stage(repository, "demand-forecast", client=client)
    run_composed_stage(repository, "allocation", client=client)
    run_composed_stage(repository, "diff", client=client)
    with repository.database.transaction() as transaction:
        transaction.execute("UPDATE endpoint_probes SET finished_at = now() - interval '2 days'")

    result = run_composed_stage(repository, "apply", client=client)

    assert result.exit_code == 5
    assert client.combos["fmo-routing_fast"] == ["old-endpoint"]
    assert not any(call[0].startswith("/api/combos/") for call in client.calls)


@pytest.mark.spec("combo-applier::Confirmed safety allows the apply stage")
@pytest.mark.spec("pipeline-orchestration::Smoke failure rolls back")
@pytest.mark.spec("combo-applier::Non-2xx smoke response is a smoke failure")
@pytest.mark.spec("combo-applier::Revert write carries an idempotency key")
def test_apply_stage_smoke_failure_rolls_back_and_maps_failures(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    client = PipelineOpsClient(smoke_status=500)
    prepare_scored_endpoint(repository, client=client)
    run_composed_stage(repository, "role-scoring", client=client)
    run_composed_stage(repository, "demand-forecast", client=client)
    run_composed_stage(repository, "allocation", client=client)
    run_composed_stage(repository, "diff", client=client)

    result = run_composed_stage(repository, "apply", client=client)

    assert result.exit_code == 6
    assert client.combos["fmo-routing_fast"] == ["old-endpoint"]
    rollback_put = next(
        call
        for call in client.calls
        if call[0] == "/api/combos/fmo-routing_fast" and call[1]["models"] == ["old-endpoint"]
    )
    assert rollback_put[3] == ComboApplier({"fmo-routing_fast": ["old-endpoint"]}).state_hash("fmo-routing_fast")

    rollback_client = PipelineOpsClient(smoke_status=500, rollback_fails=True)
    rollback_repository = Repository(Database(postgres_url))
    rollback_result = run_composed_stage(rollback_repository, "apply", client=rollback_client)
    assert rollback_result.exit_code == 7


@pytest.mark.spec("combo-applier::Empty completion is a smoke failure")
def test_apply_stage_empty_smoke_completion_rolls_back(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    client = PipelineOpsClient(smoke_status=204)
    prepare_scored_endpoint(repository, client=client)
    run_composed_stage(repository, "role-scoring", client=client)
    run_composed_stage(repository, "demand-forecast", client=client)
    run_composed_stage(repository, "allocation", client=client)
    run_composed_stage(repository, "diff", client=client)

    result = run_composed_stage(repository, "apply", client=client)

    assert result.exit_code == 6
    assert client.combos["fmo-routing_fast"] == ["old-endpoint"]


@pytest.mark.spec("combo-applier::Live state diverged from diff-time before")
@pytest.mark.spec("combo-applier::Drift guard uses structured baseline")
def test_apply_stage_blocks_when_live_combo_diverged_from_diff_before(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    client = PipelineOpsClient()
    prepare_scored_endpoint(repository, client=client)
    run_composed_stage(repository, "role-scoring", client=client)
    run_composed_stage(repository, "demand-forecast", client=client)
    run_composed_stage(repository, "allocation", client=client)
    run_composed_stage(repository, "diff", client=client)
    client.combos["fmo-routing_fast"] = ["manual-live"]

    result = run_composed_stage(repository, "apply", client=client)

    assert result.exit_code == 5
    assert client.combos["fmo-routing_fast"] == ["manual-live"]
    assert not any(call[0].startswith("/api/combos/") for call in client.calls)
    assert client.deleted_paths == []


@pytest.mark.spec("combo-applier::Non-existent combo is not created")
@pytest.mark.spec("combo-applier::Combos are never deleted")
def test_apply_stage_skips_absent_combo_without_create_or_delete(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    seed_apply_ready_diff(
        repository, role_id="missing", combo_id="fmo-missing", before=[], after_model_id="free-missing"
    )
    client = PipelineOpsClient()

    result = run_composed_stage(repository, "apply", client=client)

    assert result.exit_code == 0
    assert "fmo-missing" not in client.combos
    assert not any(call[0] == "/api/combos/fmo-missing" for call in client.calls)
    assert client.deleted_paths == []
    assert result.stage_results[0]["details"]["unmanaged_combos"] == ["fmo-missing"]
    assert result.stage_results[0]["details"]["effect"] == "idempotent_no_change"


@pytest.mark.spec("combo-applier::Absent combo is skipped without failing the run")
@pytest.mark.spec("combo-applier::Combos are never deleted")
@pytest.mark.spec("combo-applier::Production apply smoke-tests applied combos")
def test_apply_stage_skips_absent_combo_and_rebalances_present_combo(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    present_endpoint = seed_apply_ready_diff(
        repository,
        role_id="routing_fast",
        combo_id="fmo-routing_fast",
        before=["old-endpoint"],
        after_model_id="free-present",
    )
    seed_apply_ready_diff(
        repository, role_id="missing", combo_id="fmo-missing", before=[], after_model_id="free-missing"
    )
    client = PipelineOpsClient()

    result = run_composed_stage(repository, "apply", client=client)

    assert result.exit_code == 0
    assert present_endpoint
    assert client.combos["fmo-routing_fast"] == [structured_combo_step(model_id="free-present")]
    assert "fmo-missing" not in client.combos
    assert any(call[0] == "/api/combos/fmo-routing_fast" for call in client.calls)
    assert not any(call[0] == "/api/combos/fmo-missing" for call in client.calls)
    assert any(call[0] == "/v1/chat/completions" and call[1]["model"] == "fmo-routing_fast" for call in client.calls)
    assert client.deleted_paths == []
    assert result.stage_results[0]["details"]["unmanaged_combos"] == ["fmo-missing"]


@pytest.mark.spec("combo-applier::Later combo failure rolls back earlier applied combos")
@pytest.mark.spec("combo-applier::No combo is mutated without a persisted record")
def test_multi_combo_apply_rolls_back_earlier_combo_on_later_smoke_failure(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    seed_apply_ready_diff(repository, role_id="a", combo_id="fmo-a", before=["old-a"], after_model_id="free-a")
    seed_apply_ready_diff(repository, role_id="b", combo_id="fmo-b", before=["old-b"], after_model_id="free-b")
    client = MultiComboOpsClient(repository, fail_smoke_for={"fmo-b"})

    result = run_composed_stage(repository, "apply", client=client)

    with repository.database.transaction() as transaction:
        applied = transaction.execute(
            "SELECT count(*) AS total FROM combo_snapshots WHERE phase = 'applied'"
        ).fetchone()
    assert result.exit_code == 6
    assert client.combos["fmo-a"] == ["old-a"]
    assert client.combos["fmo-b"] == ["old-b"]
    assert client.applied_record_seen_before_second_mutation is True
    assert applied["total"] == 0


@pytest.mark.spec("combo-applier::Restore failure during partial rollback")
def test_multi_combo_apply_reports_rollback_failed_when_earlier_restore_fails(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    seed_apply_ready_diff(repository, role_id="a", combo_id="fmo-a", before=["old-a"], after_model_id="free-a")
    seed_apply_ready_diff(repository, role_id="b", combo_id="fmo-b", before=["old-b"], after_model_id="free-b")
    client = MultiComboOpsClient(repository, fail_smoke_for={"fmo-b"}, restore_fail_for={"fmo-a"})

    result = run_composed_stage(repository, "apply", client=client)

    assert result.exit_code == 7


@pytest.mark.spec("audit-rollback::rollback command reverts combos, not AA-index")
@pytest.mark.spec("combo-applier::Revert write carries an idempotency key")
@pytest.mark.spec("audit-rollback::Roll back a run")
def test_rollback_command_reverts_run_combos_and_records_audit_without_touching_aa_index(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    seed_apply_ready_diff(repository, role_id="a", combo_id="fmo-a", before=["old-a"], after_model_id="free-a")
    seed_apply_ready_diff(repository, role_id="b", combo_id="fmo-b", before=["old-b"], after_model_id="free-b")
    client = MultiComboOpsClient(repository)
    apply_result = run_composed_stage(repository, "apply", client=client)
    with repository.database.transaction() as transaction:
        transaction.execute(
            """
            INSERT INTO artificial_analysis_index_migrations (
              new_index_version, change_type, status, baseline_snapshot_json, threshold_proposal_json
            )
            VALUES ('9.9', 'major', 'rolled_out', '{}'::jsonb, '{}'::jsonb)
            """
        )

    result = run_runtime_command(repository, client, "rollback", run_id=apply_result.run_id)

    with repository.database.transaction() as transaction:
        audit_count = transaction.execute(
            "SELECT count(*) AS total FROM change_log WHERE action = 'rollback_reverted'"
        ).fetchone()["total"]
        migration = transaction.execute("SELECT status FROM artificial_analysis_index_migrations").fetchone()
    assert result.exit_code == 0
    assert client.combos["fmo-a"] == ["old-a"]
    assert client.combos["fmo-b"] == ["old-b"]
    revert_keys = {
        call[0].rsplit("/", 1)[-1]: call[3]
        for call in client.calls
        if call[0] in {"/api/combos/fmo-a", "/api/combos/fmo-b"} and call[1]["models"] in (["old-a"], ["old-b"])
    }
    assert revert_keys == {
        "fmo-a": ComboApplier({"fmo-a": ["old-a"]}).state_hash("fmo-a"),
        "fmo-b": ComboApplier({"fmo-b": ["old-b"]}).state_hash("fmo-b"),
    }
    assert audit_count == 2
    assert migration["status"] == "rolled_out"


@pytest.mark.spec("audit-rollback::rollback command reverts combos, not AA-index")
def test_rollback_command_reverts_single_role_combo(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    seed_apply_ready_diff(repository, role_id="a", combo_id="fmo-a", before=["old-a"], after_model_id="free-a")
    seed_apply_ready_diff(repository, role_id="b", combo_id="fmo-b", before=["old-b"], after_model_id="free-b")
    client = MultiComboOpsClient(repository)
    run_composed_stage(repository, "apply", client=client)

    result = run_runtime_command(repository, client, "rollback", role="a")

    assert result.exit_code == 0
    assert client.combos["fmo-a"] == ["old-a"]
    assert client.combos["fmo-b"] != ["old-b"]


@pytest.mark.spec("audit-rollback::rollback restore failure exits 7")
def test_rollback_command_restore_failure_exits_7(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    seed_apply_ready_diff(repository, role_id="a", combo_id="fmo-a", before=["old-a"], after_model_id="free-a")
    client = MultiComboOpsClient(repository, restore_fail_for={"fmo-a"})
    apply_result = run_composed_stage(repository, "apply", client=client)

    result = run_runtime_command(repository, client, "rollback", run_id=apply_result.run_id)

    assert result.exit_code == 7


@pytest.mark.spec("pipeline-orchestration::Audit persists records")
def test_audit_stage_persists_records_and_detects_drift(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    client = PipelineOpsClient()
    prepare_scored_endpoint(repository, client=client)
    run_composed_stage(repository, "role-scoring", client=client)
    run_composed_stage(repository, "demand-forecast", client=client)
    run_composed_stage(repository, "allocation", client=client)
    run_composed_stage(repository, "diff", client=client)
    run_composed_stage(repository, "apply", client=client)
    client.combos["fmo-routing_fast"] = ["manual-edit"]

    result = run_composed_stage(repository, "audit", client=client)

    with repository.database.transaction() as transaction:
        audit = transaction.execute("SELECT action, reason_codes FROM change_log").fetchone()
    assert result.exit_code == 0
    assert audit["action"] == "drift_detected"
    assert audit["reason_codes"] == ["drift_detected"]
