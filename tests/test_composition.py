from datetime import datetime, timezone
from pathlib import Path

import pytest

from fmo.artificial_analysis import AAModelMetrics, AASnapshot
from fmo.bootstrap import build_startup_config
from fmo.candidates import FreeCandidate
from fmo.composition import (
    StageAdapters,
    StageDependencies,
    _cli_result,
    build_canonical_stages,
    compose_runtime,
    stages_for_command,
)
from fmo.db import MigrationRunner
from fmo.metadata_sync import MetadataSyncResult
from fmo.persistence import Database, Repository
from fmo.pipeline import CANONICAL_STAGE_NAMES, PipelineRunner
from fmo.registry import FreeRegistry, FreeRegistrySyncOutcome
from tests._stage_effects import assert_success_has_declared_effect, effectful_success


def valid_env(**overrides):
    values = {
        "OMNIROUTE_URL": "https://omniroute.test",
        "DATABASE_URL": "postgresql://user:pass@localhost:5432/fmo",
        "HERMES_INVENTORY_MODE": "filesystem",
        "HERMES_HOME": "/tmp/hermes",
        "HERMES_AGENTS_PATH": "/tmp/hermes/agents",
        "HERMES_ROUTINES_PATH": "/tmp/hermes/routines",
        "HERMES_INVENTORY_CRON": "0 4 * * *",
    }
    values.update(overrides)
    return values


def empty_stage_adapters():
    return StageAdapters(
        registry_sync=lambda _client: FreeRegistrySyncOutcome(
            registry=FreeRegistry(models={}, pool_budgets={}),
            free_models_payload={"models": []},
            rankings_payload={"providers": []},
            model_count=0,
            drift=[],
            errors=[],
        ),
        catalog_scan=lambda _scanner, _client, _omniroute_instance_id: {},
        stage_adapters={},
    )


def empty_adapters_with_stage_effects():
    adapters = empty_stage_adapters()
    return StageAdapters(
        registry_sync=adapters.registry_sync,
        catalog_scan=adapters.catalog_scan,
        stage_adapters=effectful_stage_adapters(*CANONICAL_STAGE_NAMES[2:]),
    )


def effectful_stage_adapters(*stage_names):
    return {
        name: (lambda _deps, _context, stage_name=name: effectful_success(stage_name, "idempotent_no_change"))
        for name in stage_names
    }


class QuotaSearchClient:
    def __init__(self, answer="Provider gives 100 requests per day with hard stop."):
        self.answer = answer
        self.calls = []

    def post(self, path, payload):
        self.calls.append((path, payload))
        return {
            "answer": {"text": self.answer},
            "results": [{"title": "Docs", "url": "https://provider.example/free"}],
        }


class PipelineOpsClient(QuotaSearchClient):
    def __init__(self, *, probe_status=200, smoke_status=200, rollback_fails=False):
        super().__init__()
        self.probe_status = probe_status
        self.smoke_status = smoke_status
        self.rollback_fails = rollback_fails
        self.get_calls = []
        self.combos = {"fmo-routing_fast": ["old-endpoint"]}

    def post(self, path, payload, headers=None):
        if path == "/v1/search":
            return super().post(path, payload)
        if path.startswith("/api/combos/"):
            combo_id = path.rsplit("/", 1)[-1]
            if self.rollback_fails and payload.get("models") == ["old-endpoint"]:
                raise RuntimeError("rollback failed")
            self.calls.append((path, payload, headers))
            self.combos[combo_id] = list(payload["models"])
            return {"ok": True}
        if path == "/v1/chat/completions":
            self.calls.append((path, payload, headers))
            return {"status_code": self.smoke_status, "content": "ok" if self.smoke_status == 200 else ""}
        self.calls.append((path, payload, headers))
        return {"status_code": self.probe_status, "content": "ok" if self.probe_status == 200 else ""}

    def get(self, path):
        self.get_calls.append(path)
        if path == "/api/usage/analytics":
            return {
                "byProvider": [{"provider": "provider-a", "requests": 10, "successRatePct": 90, "avgLatencyMs": 120}],
                "byModel": [
                    {
                        "provider": "provider-a",
                        "model": "free-chat",
                        "requests": 5,
                        "successRatePct": 100,
                        "avgLatencyMs": 80,
                    }
                ],
            }
        if path == "/api/usage/quota":
            return {
                "meta": {"generatedAt": datetime.now(timezone.utc).isoformat()},
                "providers": [
                    {
                        "provider": "provider-a",
                        "connectionId": "conn-provider-a",
                        "quotaTotal": 100,
                        "quotaUsed": 40,
                        "resetAt": "2026-06-21T00:00:00+00:00",
                    }
                ],
            }
        if path == "/api/combos":
            return {"combos": [{"id": combo_id, "models": models} for combo_id, models in self.combos.items()]}
        raise AssertionError(f"unexpected GET {path}")


def seed_endpoint(repository, *, model_id="free-chat"):
    with repository.database.transaction() as transaction:
        provider = repository.providers.upsert(
            transaction,
            omniroute_instance_id="local",
            omniroute_provider_id="provider-a",
            provider_type="api",
        )
        account = repository.provider_accounts.upsert(
            transaction,
            provider_id=provider["id"],
            omniroute_connection_id="conn-provider-a",
        )
        endpoint = repository.provider_endpoints.upsert(
            transaction,
            provider_account_id=account["id"],
            provider_model_id=model_id,
            lifecycle_status="discovered",
            access_status="access_pending",
            metadata_hash=f"{model_id}:hash",
        )
    return endpoint


def run_composed_stage(repository, stage_name, *, client=None):
    dependencies = StageDependencies(repository=repository, omniroute_client=client or PipelineOpsClient())
    stages = build_canonical_stages(dependencies=dependencies, metadata_sync=lambda **_kwargs: None)
    selected = stages_for_command(_command_for_stage(stage_name), stages)
    return PipelineRunner(repository, stages=selected).run(trigger=stage_name, run_type=stage_name)


def _command_for_stage(stage_name):
    commands = {
        "model-matching": "match-models",
        "quota-research": "research-quotas",
        "access-classification": "classify-access",
        "probing": "probe-models",
        "telemetry-sync": "sync-telemetry",
        "quota-sync": "sync-quotas",
        "role-scoring": "score-roles",
        "allocation": "allocate",
        "diff": "diff",
        "apply": "apply",
        "audit": "rollback",
    }
    return commands[stage_name]


def prepare_confirmed_endpoint(repository, *, client=None):
    seed_endpoint(repository)
    run_composed_stage(repository, "model-matching", client=client)
    run_composed_stage(repository, "quota-research", client=client)
    run_composed_stage(repository, "access-classification", client=client)


def prepare_scored_endpoint(repository, *, client=None):
    prepare_confirmed_endpoint(repository, client=client)
    run_composed_stage(repository, "probing", client=client)
    run_composed_stage(repository, "telemetry-sync", client=client)
    run_composed_stage(repository, "quota-sync", client=client)
    with repository.database.transaction() as transaction:
        repository.roles.upsert(
            transaction,
            role_id="routing_fast",
            requirements={"capabilities": []},
            expected_load={"requests": 10},
            criticality=1,
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


@pytest.mark.spec("pipeline-orchestration::Quota research persists capped rules")
def test_quota_research_stage_persists_snapshot_and_capped_rule(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    seed_endpoint(repository)
    run_composed_stage(repository, "model-matching")
    client = QuotaSearchClient()

    result = run_composed_stage(repository, "quota-research", client=client)

    with repository.database.transaction() as transaction:
        snapshot_count = transaction.execute("SELECT count(*) AS total FROM quota_source_snapshots").fetchone()["total"]
        rule = transaction.execute("SELECT confidence, limits FROM quota_rules").fetchone()
    assert result.exit_code == 0
    assert result.stage_results[0]["details"]["effect"] == "repository_write"
    assert client.calls[0][0] == "/v1/search"
    assert snapshot_count == 1
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
    dependencies = StageDependencies(repository=repository, omniroute_client=PipelineOpsClient())
    adapters = StageAdapters(
        registry_sync=empty_stage_adapters().registry_sync,
        catalog_scan=empty_stage_adapters().catalog_scan,
    )
    stages = build_canonical_stages(
        dependencies=dependencies,
        metadata_sync=lambda **_kwargs: MetadataSyncResult(candidates={}, aa_snapshot=AASnapshot(index_version="4.1", models=())),
        adapters=adapters,
    )

    result = PipelineRunner(repository, stages=stages).run(trigger="manual", run_type="full")

    assert result.exit_code == 0
    assert [record["name"] for record in result.stage_results] == [
        "external-metadata-sync",
        "free-candidate-discovery",
        "model-matching",
        "quota-research",
        "access-classification",
        "probing",
        "telemetry-sync",
        "quota-sync",
        "role-scoring",
        "allocation",
        "diff",
        "apply",
        "audit",
    ]
    assert result.stage_results[-1]["status"] == "success"


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
        observation = transaction.execute("SELECT limit_value, used_value, remaining_value FROM quota_observations").fetchone()
        access = transaction.execute("SELECT effective_remaining FROM endpoint_access_states").fetchone()
    assert result.exit_code == 0
    assert result.stage_results[0]["details"]["effect"] == "repository_write"
    assert client.get_calls[-1] == "/api/usage/quota"
    assert float(observation["limit_value"]) == 100.0
    assert float(observation["used_value"]) == 40.0
    assert float(observation["remaining_value"]) == 60.0
    assert access["effective_remaining"]["requests"] == 60.0


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


@pytest.mark.spec("pipeline-orchestration::Allocation persists one combo plan per role")
@pytest.mark.spec("pipeline-orchestration::Oversubscription gate blocks zero-capacity pool")
def test_allocation_stage_persists_plan_and_constraint_report(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    client = PipelineOpsClient()
    prepare_scored_endpoint(repository, client=client)
    run_composed_stage(repository, "role-scoring", client=client)

    result = run_composed_stage(repository, "allocation", client=client)

    with repository.database.transaction() as transaction:
        plan = transaction.execute("SELECT role_id, status, targets, constraint_report FROM allocation_plans").fetchone()
    assert result.exit_code == 0
    assert result.stage_results[0]["details"]["effect"] == "repository_write"
    assert plan["role_id"] == "routing_fast"
    assert plan["status"] == "planned"
    assert len(plan["targets"]) == 1
    assert plan["constraint_report"]["apply"] is True


@pytest.mark.spec("pipeline-orchestration::Diff is computed without mutating OmniRoute")
def test_diff_stage_persists_minimal_diff_without_mutating_omniroute(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    client = PipelineOpsClient()
    prepare_scored_endpoint(repository, client=client)
    run_composed_stage(repository, "role-scoring", client=client)
    run_composed_stage(repository, "allocation", client=client)

    result = run_composed_stage(repository, "diff", client=client)

    with repository.database.transaction() as transaction:
        snapshot = transaction.execute("SELECT phase, state_json FROM combo_snapshots").fetchone()
    assert result.exit_code == 0
    assert result.stage_results[0]["details"]["effect"] == "repository_write"
    assert client.get_calls[-1] == "/api/combos"
    assert not any(call[0].startswith("/api/combos") for call in client.calls)
    assert snapshot["phase"] == "diff"
    assert snapshot["state_json"]["remove"] == ["old-endpoint"]


@pytest.mark.spec("pipeline-orchestration::Production apply runs the real smoke test")
@pytest.mark.spec("combo-applier::Production apply smoke-tests applied combos")
@pytest.mark.spec("combo-applier::Fabricated smoke signal rejected")
def test_apply_stage_mutates_fmo_combo_and_reports_real_smoke_signal(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    client = PipelineOpsClient()
    prepare_scored_endpoint(repository, client=client)
    run_composed_stage(repository, "role-scoring", client=client)
    run_composed_stage(repository, "allocation", client=client)
    run_composed_stage(repository, "diff", client=client)

    result = run_composed_stage(repository, "apply", client=client)

    assert result.exit_code == 0
    assert result.stage_results[0]["details"]["combo_test_called"] is True
    assert _cli_result(result).combo_test_called is True
    assert any(call[0] == "/v1/chat/completions" for call in client.calls)
    assert not any(call[0] == "/api/combos/test" for call in client.calls)
    assert client.combos["fmo-routing_fast"] != ["old-endpoint"]


@pytest.mark.spec("pipeline-orchestration::Failing guard blocks apply")
def test_apply_stage_guard_failure_blocks_mutation(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    client = PipelineOpsClient()

    result = run_composed_stage(repository, "apply", client=client)

    assert result.exit_code == 5
    assert client.combos["fmo-routing_fast"] == ["old-endpoint"]


@pytest.mark.spec("pipeline-orchestration::Smoke failure rolls back")
def test_apply_stage_smoke_failure_rolls_back_and_maps_failures(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    client = PipelineOpsClient(smoke_status=500)
    prepare_scored_endpoint(repository, client=client)
    run_composed_stage(repository, "role-scoring", client=client)
    run_composed_stage(repository, "allocation", client=client)
    run_composed_stage(repository, "diff", client=client)

    result = run_composed_stage(repository, "apply", client=client)

    assert result.exit_code == 6
    assert client.combos["fmo-routing_fast"] == ["old-endpoint"]

    rollback_client = PipelineOpsClient(smoke_status=500, rollback_fails=True)
    rollback_repository = Repository(Database(postgres_url))
    rollback_result = run_composed_stage(rollback_repository, "apply", client=rollback_client)
    assert rollback_result.exit_code == 7


@pytest.mark.spec("pipeline-orchestration::Audit persists records")
def test_audit_stage_persists_records_and_detects_drift(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    client = PipelineOpsClient()
    prepare_scored_endpoint(repository, client=client)
    run_composed_stage(repository, "role-scoring", client=client)
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

    cli_result = runtime.run_scheduler_once("2026-06-19T04:00:00Z")

    repository = Repository(Database(postgres_url))
    with repository.database.transaction() as transaction:
        runs = [run for run in repository.runs.list(transaction) if run["run_type"] == "full"]
    assert cli_result.exit_code == 0
    assert len(runs) == 1
    assert runs[0]["trigger"] == "scheduled"
    assert runs[0]["run_type"] == "full"


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
        metadata_sync=lambda **_kwargs: MetadataSyncResult(candidates={}, aa_snapshot=AASnapshot(index_version="4.1", models=())),
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
        metadata_sync=lambda **_kwargs: MetadataSyncResult(candidates={}, aa_snapshot=AASnapshot(index_version="4.1", models=())),
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
        "role-scoring",
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
        "model-matching",
    ]
    assert stages[-1]["status"] == "not_implemented"
    assert stages[-1]["reason"] == "model-matching adapter is not wired"
