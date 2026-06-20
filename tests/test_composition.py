from pathlib import Path

import pytest

from fmo.artificial_analysis import AAModelMetrics, AASnapshot
from fmo.bootstrap import build_startup_config
from fmo.candidates import FreeCandidate
from fmo.composition import StageAdapters, build_canonical_stages, compose_runtime
from fmo.db import MigrationRunner
from fmo.metadata_sync import MetadataSyncResult
from fmo.persistence import Database, Repository
from fmo.pipeline import CANONICAL_STAGE_NAMES
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
