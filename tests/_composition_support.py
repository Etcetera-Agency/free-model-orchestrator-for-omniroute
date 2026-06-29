import argparse
from datetime import UTC, datetime, timedelta
from pathlib import Path

from psycopg.types.json import Jsonb

from fmo.accounts import AccountDiscoveryOutcome
from fmo.artificial_analysis import AAModelMetrics, AASnapshot
from fmo.bootstrap import build_startup_config
from fmo.candidates import FreeCandidate
from fmo.composition import (
    ComposedRuntime,
    StageAdapters,
    StageDependencies,
    _cli_result,
    build_canonical_stages,
    build_production_llm_runtime,
    compose_runtime,
    select_llm_model,
    stages_for_command,
)
from fmo.db import MigrationRunner
from fmo.hermes_inventory import Consumer, Inventory
from fmo.metadata_sync import MetadataSyncResult
from fmo.persistence import Database, Repository
from fmo.pipeline import CANONICAL_STAGE_NAMES, PipelineRunner
from fmo.registry import FreeRegistry, FreeRegistrySyncOutcome
from tests._clients import (
    OPENAI_CHAT_COMPLETION_BODY,
    AccountDiscoveryOpsClient,
    FakeInstructorClient,
    FakeOpenAIClient,
    MultiComboOpsClient,
    PipelineOpsClient,
    RecordingLlmRuntime,
)
from tests._fixtures import load_hermes_fixture
from tests._stage_effects import assert_success_has_declared_effect, effectful_success

__all__ = [
    "CANONICAL_STAGE_NAMES",
    "OPENAI_CHAT_COMPLETION_BODY",
    "UTC",
    "AAModelMetrics",
    "AASnapshot",
    "AccountDiscoveryOpsClient",
    "ComposedRuntime",
    "Database",
    "FakeInstructorClient",
    "FakeOpenAIClient",
    "FreeCandidate",
    "FreeRegistry",
    "FreeRegistrySyncOutcome",
    "MetadataSyncResult",
    "MigrationRunner",
    "MultiComboOpsClient",
    "Path",
    "PipelineOpsClient",
    "PipelineRunner",
    "RecordingLlmRuntime",
    "Repository",
    "StageAdapters",
    "StageDependencies",
    "_cli_result",
    "argparse",
    "assert_success_has_declared_effect",
    "build_canonical_stages",
    "build_production_llm_runtime",
    "build_startup_config",
    "compose_runtime",
    "datetime",
    "effectful_success",
    "empty_adapters_with_stage_effects",
    "empty_stage_adapters",
    "hermes_inventory_fixture",
    "prepare_confirmed_endpoint",
    "prepare_scored_endpoint",
    "run_composed_stage",
    "run_composed_stage_with_dependencies",
    "run_rebalance_stages",
    "run_runtime_command",
    "seed_confirmed_llm_candidate",
    "seed_endpoint",
    "seed_free_registry_snapshot",
    "select_llm_model",
    "structured_combo_step",
    "timedelta",
    "valid_env",
]


def valid_env(**overrides):
    values = {
        "OMNIROUTE_URL": "https://omniroute.test",
        "OMNIROUTE_API_KEY": "test-key",
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
        account_discovery=lambda _client, previous_pools=None: AccountDiscoveryOutcome(
            connections=[],
            pools={},
            rate_limits_available=True,
            errors=[],
        ),
        stage_adapters={},
    )


def empty_adapters_with_stage_effects():
    adapters = empty_stage_adapters()
    return StageAdapters(
        registry_sync=adapters.registry_sync,
        catalog_scan=adapters.catalog_scan,
        account_discovery=adapters.account_discovery,
        stage_adapters=effectful_stage_adapters(*CANONICAL_STAGE_NAMES[2:]),
    )


def hermes_inventory_fixture():
    cron = load_hermes_fixture("cron_jobs.json")["jobs"][0]
    return Inventory(
        consumers=[
            Consumer(
                role_id=str(cron["model"]),
                consumer_type="cron_job",
                consumer=str(cron["id"]),
                cadence=str(cron["schedule"]["expr"]),
                calls_per_run=12,
            )
        ]
    )


def effectful_stage_adapters(*stage_names):
    return {
        name: (lambda _deps, _context, stage_name=name: effectful_success(stage_name, "idempotent_no_change"))
        for name in stage_names
    }


def seed_endpoint(repository, *, model_id="free-chat", provider_id="provider-a", connection_id="conn-provider-a"):
    with repository.database.transaction() as transaction:
        provider = repository.providers.upsert(
            transaction,
            omniroute_instance_id="local",
            omniroute_provider_id=provider_id,
            provider_type="api",
        )
        account = repository.provider_accounts.upsert(
            transaction,
            provider_id=provider["id"],
            omniroute_connection_id=connection_id,
        )
        return repository.provider_endpoints.upsert(
            transaction,
            provider_account_id=account["id"],
            provider_model_id=model_id,
            lifecycle_status="discovered",
            access_status="access_pending",
            metadata_hash=f"{model_id}:hash",
        )


def seed_free_registry_snapshot(repository, *, models, created_at):
    payload = {
        "free_models": {
            "models": [{"provider": provider, "modelId": model_id, "freeType": "free"} for provider, model_id in models]
        },
        "rankings": {"providers": []},
    }
    with repository.database.transaction() as transaction:
        transaction.execute(
            """
            INSERT INTO free_provider_registry_snapshots (
              free_models_hash, rankings_hashes, raw_json, created_at
            )
            VALUES (
              %(hash)s, '{}'::jsonb, %(payload)s, %(created_at)s
            )
            """,
            {
                "hash": f"{created_at.isoformat()}:{models}",
                "payload": Jsonb(payload),
                "created_at": created_at,
            },
        )
        for provider, model_id in models:
            transaction.execute(
                """
                INSERT INTO free_model_definitions (
                  provider_id, provider_model_id, free_type, omniroute_pool_key,
                  source_snapshot_id, status, last_seen_at
                )
                SELECT %(provider)s, %(model_id)s, 'free', %(pool_key)s,
                       id, 'active', %(created_at)s
                FROM free_provider_registry_snapshots
                WHERE free_models_hash = %(hash)s
                ON CONFLICT (provider_id, provider_model_id)
                DO UPDATE SET
                  free_type = EXCLUDED.free_type,
                  omniroute_pool_key = EXCLUDED.omniroute_pool_key,
                  source_snapshot_id = EXCLUDED.source_snapshot_id,
                  status = EXCLUDED.status,
                  last_seen_at = EXCLUDED.last_seen_at
                """,
                {
                    "provider": provider,
                    "model_id": model_id,
                    "pool_key": f"{provider}:{model_id}",
                    "hash": f"{created_at.isoformat()}:{models}",
                    "created_at": created_at,
                },
            )


def run_composed_stage(repository, stage_name, *, client=None):
    dependencies = StageDependencies(repository=repository, omniroute_client=client or PipelineOpsClient())
    stages = build_canonical_stages(dependencies=dependencies, metadata_sync=lambda **_kwargs: None)
    selected = stages_for_command(_command_for_stage(stage_name), stages)
    return PipelineRunner(repository, stages=selected).run(trigger=stage_name, run_type=stage_name)


def run_composed_stage_with_dependencies(repository, stage_name, dependencies):
    stages = build_canonical_stages(dependencies=dependencies, metadata_sync=lambda **_kwargs: None)
    selected = stages_for_command(_command_for_stage(stage_name), stages)
    return PipelineRunner(repository, stages=selected).run(trigger=stage_name, run_type=stage_name)


def run_runtime_command(repository, client, command, **args):
    dependencies = StageDependencies(repository=repository, omniroute_client=client)
    runtime = ComposedRuntime(
        repository=repository,
        omniroute_client=client,
        stages=build_canonical_stages(dependencies=dependencies, metadata_sync=lambda **_kwargs: None),
        cron="0 4 * * *",
        llm_runtime=None,
        config=build_startup_config(valid_env()),
    )
    values = {
        "dry_run": False,
        "run_id": None,
        "endpoint": None,
        "role": None,
    }
    values.update(args)
    return runtime.run_command(command, argparse.Namespace(**values))


def run_rebalance_stages(repository, client):
    stage_names = [
        "access-classification",
        "probing",
        "telemetry-sync",
        "role-scoring",
        "demand-forecast",
    ]
    return [run_composed_stage(repository, stage_name, client=client) for stage_name in stage_names]


def _command_for_stage(stage_name):
    commands = {
        "model-matching": "match-models",
        "account-discovery": "discover-accounts",
        "access-classification": "classify-access",
        "probing": "probe-models",
        "telemetry-sync": "sync-telemetry",
        "hermes-inventory": "sync-hermes-inventory",
        "role-lifecycle": "reconcile-roles",
        "role-scoring": "score-roles",
        "demand-forecast": "forecast-demand",
        "audit": "full",
    }
    return commands[stage_name]


def prepare_confirmed_endpoint(repository, *, client=None):
    seed_endpoint(repository)
    run_composed_stage(repository, "model-matching", client=client)
    run_composed_stage(repository, "access-classification", client=client)


def prepare_scored_endpoint(repository, *, client=None):
    prepare_confirmed_endpoint(repository, client=client)
    run_composed_stage(repository, "probing", client=client)
    run_composed_stage(repository, "telemetry-sync", client=client)
    with repository.database.transaction() as transaction:
        repository.roles.upsert(
            transaction,
            role_id="routing_fast",
            requirements={"capabilities": []},
            expected_load={"requests": 10},
            criticality=1,
        )


def seed_confirmed_llm_candidate(
    repository,
    *,
    model_id,
    intelligence_index,
    remaining=100,
    health_status="active",
    context_window=32768,
    coding_index=None,
    agentic_index=None,
    aa_latency=None,
    aa_index_version="4.1",
    provider_id="provider-a",
    connection_id="pool-a",
    omniroute_instance_id="local",
):
    with repository.database.transaction() as transaction:
        canonical = repository.canonical_models.upsert(transaction, canonical_slug=model_id)
        provider = repository.providers.upsert(
            transaction,
            omniroute_instance_id=omniroute_instance_id,
            omniroute_provider_id=provider_id,
            provider_type="api",
        )
        account = repository.provider_accounts.upsert(
            transaction,
            provider_id=provider["id"],
            omniroute_connection_id=connection_id,
        )
        endpoint = repository.provider_endpoints.upsert(
            transaction,
            provider_account_id=account["id"],
            provider_model_id=model_id,
            lifecycle_status="active",
            access_status="confirmed",
            probe_status="passed",
            metadata_hash=f"{model_id}:hash",
        )
        transaction.execute(
            """
            UPDATE provider_endpoints
            SET canonical_model_id = %(model_id)s,
                advertised_context_window = %(context_window)s,
                provider_context_window = %(context_window)s,
                probed_context_window = %(context_window)s,
                effective_context_window = %(context_window)s
            WHERE id = %(endpoint_id)s
            """,
            {"model_id": canonical["id"], "endpoint_id": endpoint["id"], "context_window": context_window},
        )
        transaction.execute(
            """
            INSERT INTO free_model_definitions (provider_id, provider_model_id, free_type, omniroute_pool_key, status)
            VALUES (%(provider_id)s, %(model_id)s, 'free', %(pool_key)s, 'active')
            ON CONFLICT (provider_id, provider_model_id)
            DO UPDATE SET status = EXCLUDED.status
            """,
            {"provider_id": provider_id, "model_id": model_id, "pool_key": connection_id},
        )
        transaction.execute(
            """
            INSERT INTO endpoint_access_states (
              endpoint_id, status, reason_code, effective_remaining,
              reset_at, hard_stop_capable, evidence
            )
            VALUES (
              %(endpoint_id)s, 'confirmed', 'free_quota_available',
              %(remaining)s, null, true, %(evidence)s
            )
            ON CONFLICT (endpoint_id)
            DO UPDATE SET effective_remaining = EXCLUDED.effective_remaining
            """,
            {
                "endpoint_id": endpoint["id"],
                "remaining": Jsonb({"requests": remaining}),
                "evidence": Jsonb(
                    {
                        "remaining_source": "live_observed",
                        "daily_budget_source": "research",
                        "percent_remaining": 100,
                        "locked_out": False,
                        "safety_buffer": 1.0,
                    }
                ),
            },
        )
        transaction.execute(
            """
            INSERT INTO artificial_analysis_model_metrics (
              canonical_model_id, intelligence_index, coding_index, agentic_index,
              median_end_to_end_seconds, index_version, source_payload_hash, stale_after
            )
            VALUES (
              %(model_id)s, %(index)s, %(coding_index)s, %(agentic_index)s,
              %(aa_latency)s, %(index_version)s, %(hash)s, now() + interval '1 day'
            )
            """,
            {
                "model_id": canonical["id"],
                "index": intelligence_index,
                "coding_index": coding_index,
                "agentic_index": agentic_index,
                "aa_latency": aa_latency,
                "index_version": aa_index_version,
                "hash": f"{model_id}:aa",
            },
        )
        transaction.execute(
            """
            INSERT INTO endpoint_health_observations (endpoint_id, granularity, status, observed_at)
            VALUES (%(endpoint_id)s, 'model', %(status)s, now())
            """,
            {"endpoint_id": endpoint["id"], "status": health_status},
        )
    return endpoint


def structured_combo_step(*, model_id, provider_id="provider-a", connection_id="pool-a"):
    step = {
        "kind": "model",
        "model": model_id,
        "providerId": provider_id,
        "weight": 0,
    }
    if connection_id:
        step["connectionId"] = connection_id
    return step
