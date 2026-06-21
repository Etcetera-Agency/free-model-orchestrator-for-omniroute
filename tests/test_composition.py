import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
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
from fmo.composition_stages import _smoke_combo
from fmo.db import MigrationRunner
from fmo.omniroute import OmniRouteRequestError
from fmo.aa_migration import MigrationProposalResponse
from fmo.hermes_inventory import Consumer, Inventory, InspectorForecastResponse
from fmo.metadata_sync import MetadataSyncResult
from fmo.persistence import Database, Repository
from fmo.pipeline import CANONICAL_STAGE_NAMES, PipelineRunner
from fmo.quota_research import QuotaClaimResponse
from fmo.registry import FreeRegistry, FreeRegistrySyncOutcome
from fmo.smart_review import ComboReviewResponse
from tests._stage_effects import assert_success_has_declared_effect, effectful_success


OPENAI_CHAT_COMPLETION_BODY = {
    "id": "chatcmpl-fmo-smoke",
    "object": "chat.completion",
    "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}],
}


EMPTY_OPENAI_CHAT_COMPLETION_BODY = {
    "id": "chatcmpl-fmo-smoke-empty",
    "object": "chat.completion",
    "choices": [{"index": 0, "message": {"role": "assistant", "content": ""}, "finish_reason": "stop"}],
}


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
    return Inventory(
        consumers=[
            Consumer(
                role_id="routing_fast",
                consumer_type="cron_job",
                consumer="daily-routing",
                cadence="0 4 * * *",
                calls_per_run=12,
            )
        ]
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
        self.deleted_paths = []

    def post(self, path, payload, headers=None, idempotency_key=None):
        if path == "/v1/search":
            return super().post(path, payload)
        if path.startswith("/api/combos/"):
            combo_id = path.rsplit("/", 1)[-1]
            if self.rollback_fails and payload.get("models") == ["old-endpoint"]:
                raise RuntimeError("rollback failed")
            self.calls.append((path, payload, headers, idempotency_key))
            self.combos[combo_id] = list(payload["models"])
            return {"ok": True}
        if path == "/v1/chat/completions":
            self.calls.append((path, payload, headers, idempotency_key))
            if self.smoke_status >= 400:
                raise OmniRouteRequestError("POST", path, self.smoke_status)
            if self.smoke_status == 204:
                return EMPTY_OPENAI_CHAT_COMPLETION_BODY
            return OPENAI_CHAT_COMPLETION_BODY
        self.calls.append((path, payload, headers, idempotency_key))
        return {"status_code": self.probe_status, "content": "ok" if self.probe_status == 200 else ""}

    def delete(self, path):
        self.deleted_paths.append(path)
        raise AssertionError(f"unexpected DELETE {path}")

    def get(self, path):
        self.get_calls.append(path)
        if path == "/api/providers":
            return {
                "connections": [
                    {
                        "id": "conn-provider-a",
                        "provider": "provider-a",
                        "enabled": True,
                        "upstream_account_id": "acct-provider-a",
                        "status": "confirmed",
                        "quota": 100,
                    }
                ]
            }
        if path == "/api/rate-limits":
            return {
                "connections": [
                    {
                        "connectionId": "conn-provider-a",
                        "provider": "provider-a",
                        "enabled": True,
                        "remaining": 100,
                    }
                ]
            }
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
                        "resetAt": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
                    }
                ],
            }
        if path == "/api/combos":
            return {"combos": [{"id": combo_id, "models": models} for combo_id, models in self.combos.items()]}
        raise AssertionError(f"unexpected GET {path}")


class MultiComboOpsClient(PipelineOpsClient):
    def __init__(self, repository, *, fail_smoke_for=None, restore_fail_for=None):
        super().__init__()
        self.repository = repository
        self.fail_smoke_for = set(fail_smoke_for or [])
        self.restore_fail_for = set(restore_fail_for or [])
        self.combos = {
            "fmo-a": ["old-a"],
            "fmo-b": ["old-b"],
        }
        self.applied_record_seen_before_second_mutation = False

    def post(self, path, payload, headers=None, idempotency_key=None):
        if path.startswith("/api/combos/"):
            combo_id = path.rsplit("/", 1)[-1]
            if combo_id == "fmo-b" and payload.get("models") != self._before_models(combo_id):
                self.applied_record_seen_before_second_mutation = self._applied_record_exists("fmo-a")
            if combo_id in self.restore_fail_for and payload.get("models") == self._before_models(combo_id):
                raise RuntimeError("restore failed")
        if path == "/v1/chat/completions":
            combo_id = payload["model"]
            self.calls.append((path, payload, headers, idempotency_key))
            if combo_id in self.fail_smoke_for:
                return EMPTY_OPENAI_CHAT_COMPLETION_BODY
            return OPENAI_CHAT_COMPLETION_BODY
        return super().post(path, payload, headers, idempotency_key)

    def _applied_record_exists(self, combo_id):
        with self.repository.database.transaction() as transaction:
            row = transaction.execute(
                """
                SELECT 1
                FROM combo_snapshots
                WHERE omniroute_combo_id = %(combo_id)s
                  AND phase = 'applied'
                LIMIT 1
                """,
                {"combo_id": combo_id},
            ).fetchone()
        return row is not None

    def _before_models(self, combo_id):
        return {"fmo-a": ["old-a"], "fmo-b": ["old-b"]}[combo_id]


class AccountDiscoveryOpsClient(PipelineOpsClient):
    def __init__(self, *, rate_limits_fail=False, connections=None):
        super().__init__()
        self.rate_limits_fail = rate_limits_fail
        self.connections = connections or [
            {
                "id": "conn-a",
                "provider": "provider-a",
                "enabled": True,
                "upstream_account_id": "shared-account",
                "status": "confirmed",
                "quota": 100,
            },
            {
                "id": "conn-b",
                "provider": "provider-a",
                "enabled": True,
                "upstream_account_id": "shared-account",
                "status": "confirmed",
                "quota": 100,
            },
        ]

    def get(self, path):
        self.get_calls.append(path)
        if path == "/api/providers":
            return {"connections": self.connections}
        if path == "/api/rate-limits":
            if self.rate_limits_fail:
                raise OmniRouteRequestError("GET", path, 500)
            return {
                "connections": [
                    {"connectionId": connection["id"], "provider": connection["provider"], "enabled": True}
                    for connection in self.connections
                ]
            }
        return super().get(path)


class RecordingLlmRuntime:
    def __init__(self, *, quota_amount=200.0, review_diffs=None, fail=False):
        self.quota_amount = quota_amount
        self.review_diffs = review_diffs or []
        self.fail = fail
        self.calls = []

    def complete(self, *, site, context, response_model):
        self.calls.append({"site": site.name, "context": context, "response_model": response_model.__name__})
        if self.fail:
            raise RuntimeError("llm unavailable")
        if response_model is QuotaClaimResponse:
            return response_model(
                metric="requests",
                amount=self.quota_amount,
                window="day",
                evidence=["https://llm.example/evidence"],
                hard_stop=True,
            )
        if response_model is ComboReviewResponse:
            return response_model(diffs=self.review_diffs)
        if response_model is InspectorForecastResponse:
            return response_model(
                role="routing_fast",
                expected_calls=25,
                average_input_tokens=100,
                average_output_tokens=50,
                confidence="medium",
            )
        if response_model is MigrationProposalResponse:
            return response_model(
                index_version="4.2",
                roles={"routing_fast": {"metric": "intelligence_index", "threshold": 60}},
            )
        raise AssertionError(f"unexpected response model {response_model}")


class FakeOpenAIClient:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class FakeInstructorCompletions:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        response_model = kwargs["response_model"]
        if response_model is MigrationProposalResponse:
            return response_model(
                index_version="4.2",
                roles={"routing_fast": {"metric": "intelligence_index", "threshold": 60}},
            )
        return response_model(metric="requests", amount=1, window="day", evidence=["fixture"], hard_stop=True)


class FakeInstructorClient:
    def __init__(self):
        self.chat = type("Chat", (), {"completions": FakeInstructorCompletions()})()


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


def _command_for_stage(stage_name):
    commands = {
        "model-matching": "match-models",
        "account-discovery": "discover-accounts",
        "quota-research": "research-quotas",
        "access-classification": "classify-access",
        "probing": "probe-models",
        "telemetry-sync": "sync-telemetry",
        "quota-sync": "sync-quotas",
        "hermes-inventory": "sync-hermes-inventory",
        "role-lifecycle": "reconcile-roles",
        "role-scoring": "score-roles",
        "demand-forecast": "forecast-demand",
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
    aa_index_version="4.1",
):
    with repository.database.transaction() as transaction:
        canonical = repository.canonical_models.upsert(transaction, canonical_slug=model_id)
        provider = repository.providers.upsert(
            transaction,
            omniroute_instance_id="local",
            omniroute_provider_id="provider-a",
            provider_type="api",
        )
        account = repository.provider_accounts.upsert(
            transaction,
            provider_id=provider["id"],
            omniroute_connection_id="pool-a",
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
            VALUES ('provider-a', %(model_id)s, 'free', 'pool-a', 'active')
            ON CONFLICT (provider_id, provider_model_id)
            DO UPDATE SET status = EXCLUDED.status
            """,
            {"model_id": model_id},
        )
        transaction.execute(
            """
            INSERT INTO endpoint_access_states (
              endpoint_id, status, reason_code, effective_remaining,
              reset_at, hard_stop_capable, evidence
            )
            VALUES (
              %(endpoint_id)s, 'confirmed', 'free_quota_available',
              %(remaining)s, now() + interval '1 day', true, '{}'::jsonb
            )
            ON CONFLICT (endpoint_id)
            DO UPDATE SET effective_remaining = EXCLUDED.effective_remaining
            """,
            {"endpoint_id": endpoint["id"], "remaining": Jsonb({"requests": remaining})},
        )
        transaction.execute(
            """
            INSERT INTO artificial_analysis_model_metrics (
              canonical_model_id, intelligence_index, coding_index, agentic_index,
              index_version, source_payload_hash, stale_after
            )
            VALUES (
              %(model_id)s, %(index)s, %(coding_index)s, %(agentic_index)s,
              %(index_version)s, %(hash)s, now() + interval '1 day'
            )
            """,
            {
                "model_id": canonical["id"],
                "index": intelligence_index,
                "coding_index": coding_index,
                "agentic_index": agentic_index,
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


def seed_apply_ready_diff(repository, *, role_id, combo_id, before, after_model_id):
    endpoint = seed_confirmed_llm_candidate(
        repository,
        model_id=after_model_id,
        intelligence_index=80,
        remaining=100,
    )
    now = datetime.now(timezone.utc)
    with repository.database.transaction() as transaction:
        repository.roles.upsert(
            transaction,
            role_id=role_id,
            requirements={"capabilities": []},
            expected_load={"requests": 1},
            criticality=1,
        )
        repository.probes.record(
            transaction,
            endpoint_id=endpoint["id"],
            suite_version="production-v1",
            probe_type="basic",
            request_hash=f"{combo_id}:probe",
            passed=True,
            http_status=200,
            started_at=now,
            finished_at=now,
            details={"suites": ["basic"], "reserved_capacity": True},
        )
        repository.combo_snapshots.upsert(
            transaction,
            role_id=role_id,
            omniroute_combo_id=combo_id,
            state_hash=f"{combo_id}:diff",
            state_json={
                "before": before,
                "after": [str(endpoint["id"])],
                "add": [str(endpoint["id"])],
                "remove": before,
            },
            phase="diff",
            run_id=None,
        )
    return str(endpoint["id"])


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
        metadata_sync=lambda **_kwargs: MetadataSyncResult(candidates={}, aa_snapshot=AASnapshot(index_version="4.1", models=())),
        adapters=adapters,
    )

    result = PipelineRunner(repository, stages=stages).run(trigger="manual", run_type="full")

    assert result.exit_code == 0
    assert [record["name"] for record in result.stage_results] == [
        "external-metadata-sync",
        "free-candidate-discovery",
        "account-discovery",
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
    assert result.stage_results[-1]["status"] == "success"


@pytest.mark.spec("pipeline-orchestration::Account discovery persists quota pools")
def test_account_discovery_stage_persists_quota_pools_and_membership(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    client = AccountDiscoveryOpsClient()

    result = run_composed_stage(repository, "account-discovery", client=client)

    with repository.database.transaction() as transaction:
        account_rows = transaction.execute(
            """
            SELECT omniroute_connection_id, quota_independence_status, quota_pool_id
            FROM provider_accounts
            ORDER BY omniroute_connection_id
            """
        ).fetchall()
        member_count = transaction.execute("SELECT count(*) AS total FROM quota_pool_members").fetchone()["total"]
        snapshot = transaction.execute("SELECT snapshot_json FROM account_discovery_snapshots").fetchone()
    assert result.exit_code == 0
    assert result.stage_results[0]["details"]["effect"] == "repository_write"
    assert client.get_calls[:2] == ["/api/providers", "/api/rate-limits"]
    assert [row["quota_independence_status"] for row in account_rows] == ["confirmed", "confirmed"]
    assert all(row["quota_pool_id"] for row in account_rows)
    assert len({row["quota_pool_id"] for row in account_rows}) == 1
    assert member_count == 2
    assert snapshot["snapshot_json"]["rate_limits_available"] is True


@pytest.mark.spec("pipeline-orchestration::Unavailable rate-limit data stays conservative")
def test_account_discovery_stage_rate_limit_failure_stays_conservative(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    client = AccountDiscoveryOpsClient(rate_limits_fail=True)

    result = run_composed_stage(repository, "account-discovery", client=client)

    with repository.database.transaction() as transaction:
        statuses = [
            row["quota_independence_status"]
            for row in transaction.execute("SELECT quota_independence_status FROM provider_accounts ORDER BY omniroute_connection_id").fetchall()
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
    assert names.index("account-discovery") < names.index("quota-sync")
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
            metadata_sync=lambda **_kwargs: MetadataSyncResult(candidates={}, aa_snapshot=AASnapshot(index_version="4.1", models=())),
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


@pytest.mark.spec("pipeline-orchestration::Account discovery persists quota pools")
def test_allocation_uses_account_quota_pool_not_per_account_capacity(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    pool_id = None
    for model_id in ["shared-a", "shared-b"]:
        endpoint = seed_confirmed_llm_candidate(repository, model_id=model_id, intelligence_index=80, remaining=1)
        with repository.database.transaction() as transaction:
            account = transaction.execute(
                """
                SELECT provider_account_id
                FROM provider_endpoints
                WHERE id = %(endpoint_id)s
                """,
                {"endpoint_id": endpoint["id"]},
            ).fetchone()
            if pool_id is None:
                pool_id = transaction.execute(
                    """
                    INSERT INTO quota_pools (name, provider_group, reset_policy)
                    VALUES ('provider-a:shared:requests', 'provider-a', '{}'::jsonb)
                    RETURNING id
                    """
                ).fetchone()["id"]
            transaction.execute(
                """
                UPDATE provider_accounts
                SET quota_pool_id = %(pool_id)s,
                    quota_independence_status = 'assumed_shared'
                WHERE id = %(account_id)s
                """,
                {"pool_id": pool_id, "account_id": account["provider_account_id"]},
            )
    with repository.database.transaction() as transaction:
        repository.roles.upsert(
            transaction,
            role_id="shared_capacity",
            requirements={"capabilities": []},
            expected_load={"requests": 2},
            criticality=1,
        )
    run_composed_stage(repository, "role-scoring")
    run_composed_stage(repository, "demand-forecast")

    result = run_composed_stage(repository, "allocation")

    with repository.database.transaction() as transaction:
        plan = transaction.execute("SELECT status, targets, constraint_report FROM allocation_plans WHERE role_id = 'shared_capacity'").fetchone()
    assert result.exit_code == 0
    assert plan["status"] == "degraded"
    assert plan["targets"] == []
    assert plan["constraint_report"]["reason"] == "no_primary"


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


@pytest.mark.spec("hermes-inventory::Inventory persisted from the selected mode")
@pytest.mark.spec("hermes-inventory::Inspector is prompt-only")
@pytest.mark.spec("pipeline-orchestration::Inventory precedes scoring")
@pytest.mark.spec("pipeline-orchestration::Schedule change refreshes forecast inputs")
def test_hermes_inventory_stage_uses_selected_adapter_and_persists_prompt_only_forecast(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    config = build_startup_config(valid_env(DATABASE_URL=postgres_url, HERMES_INVENTORY_MODE="command", HERMES_INVENTORY_COMMAND="inventory"))
    llm_runtime = RecordingLlmRuntime()
    dependencies = StageDependencies(
        repository=repository,
        omniroute_client=PipelineOpsClient(),
        config=config,
        llm_runtime=llm_runtime,
        hermes_inventory_adapter=lambda received: hermes_inventory_fixture() if received.hermes_inventory_mode == "command" else None,
    )

    result = run_composed_stage_with_dependencies(repository, "hermes-inventory", dependencies)

    with repository.database.transaction() as transaction:
        role = transaction.execute("SELECT id, expected_load, role_lifecycle_status FROM roles WHERE id = 'routing_fast'").fetchone()
        consumer = transaction.execute("SELECT consumer_key, calls_per_run FROM role_consumers").fetchone()
        inventory_run = transaction.execute("SELECT source_mode, status, roles_found, routines_found FROM hermes_inventory_runs").fetchone()
    assert result.exit_code == 0
    assert result.stage_results[0]["details"]["effect"] == "repository_write"
    assert role["expected_load"]["requests"] == 25
    assert role["role_lifecycle_status"] == "bootstrap_pending"
    assert consumer["consumer_key"] == "daily-routing"
    assert float(consumer["calls_per_run"]) == 12.0
    assert inventory_run["source_mode"] == "command"
    assert inventory_run["status"] == "completed"
    assert inventory_run["roles_found"] == 1
    assert inventory_run["routines_found"] == 1
    assert llm_runtime.calls == [
        {
            "site": "hermes-inspector",
            "context": {
                "prompt": (
                    "Hermes inventory forecast request\n"
                    "Changes:\n"
                    "Consumers:\n"
                    "routing_fast cron_job daily-routing 0 4 * * * 12"
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


@pytest.mark.spec("role-scorer::Below context minimum rejected in scoring")
@pytest.mark.spec("context-window-eligibility::Below minimum")
@pytest.mark.spec("pipeline-orchestration::Scoring stage drops below-context endpoint")
def test_role_scoring_stage_rejects_below_context_endpoint(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    endpoint = seed_confirmed_llm_candidate(repository, model_id="tiny-context", intelligence_index=80, context_window=4096)
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
        repository.roles.upsert(transaction, role_id="routing_fast", requirements={"capabilities": []}, expected_load={"requests": 1}, criticality=1)
    client = PipelineOpsClient()
    client.combos["fmo-routing_fast"] = [str(seed["id"])]

    run_composed_stage(repository, "role-scoring", client=client)
    client.combos["fmo-routing_fast"] = [str(seed["id"]), str(other["id"])]
    with repository.database.transaction() as transaction:
        transaction.execute("UPDATE roles SET minimum_quality_value = 55, maximum_quality_value = 65 WHERE id = 'routing_fast'")
    run_composed_stage(repository, "role-scoring", client=client)

    with repository.database.transaction() as transaction:
        role = transaction.execute("SELECT minimum_quality_value, maximum_quality_value FROM roles WHERE id = 'routing_fast'").fetchone()
    assert float(role["minimum_quality_value"]) == 55
    assert float(role["maximum_quality_value"]) == 65


@pytest.mark.spec("quality-gate::Re-seeding re-anchors the band")
def test_role_scoring_stage_reanchors_when_combo_is_stripped_to_single_member(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    first = seed_confirmed_llm_candidate(repository, model_id="seed-low", intelligence_index=50)
    second = seed_confirmed_llm_candidate(repository, model_id="seed-high", intelligence_index=75)
    with repository.database.transaction() as transaction:
        repository.roles.upsert(transaction, role_id="routing_fast", requirements={"capabilities": []}, expected_load={"requests": 1}, criticality=1)
    client = PipelineOpsClient()
    client.combos["fmo-routing_fast"] = [str(first["id"])]
    run_composed_stage(repository, "role-scoring", client=client)
    client.combos["fmo-routing_fast"] = [str(second["id"])]
    run_composed_stage(repository, "role-scoring", client=client)

    with repository.database.transaction() as transaction:
        role = transaction.execute("SELECT minimum_quality_value, maximum_quality_value FROM roles WHERE id = 'routing_fast'").fetchone()
    assert float(role["minimum_quality_value"]) <= 75 <= float(role["maximum_quality_value"])
    assert float(role["minimum_quality_value"]) > 50


@pytest.mark.spec("quality-gate::Paid seed anchors but is not a member")
def test_paid_seed_sets_anchor_but_is_excluded_from_allocated_members(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    paid_seed = seed_confirmed_llm_candidate(repository, model_id="paid-seed", intelligence_index=70)
    free_member = seed_confirmed_llm_candidate(repository, model_id="free-member", intelligence_index=68)
    with repository.database.transaction() as transaction:
        transaction.execute("UPDATE provider_endpoints SET access_status = 'paid' WHERE id = %(id)s", {"id": paid_seed["id"]})
        transaction.execute("DELETE FROM endpoint_access_states WHERE endpoint_id = %(id)s", {"id": paid_seed["id"]})
        repository.roles.upsert(transaction, role_id="routing_fast", requirements={"capabilities": []}, expected_load={"requests": 1}, criticality=1)
    client = PipelineOpsClient()
    client.combos["fmo-routing_fast"] = [str(paid_seed["id"])]

    run_composed_stage(repository, "role-scoring", client=client)
    run_composed_stage(repository, "demand-forecast", client=client)
    run_composed_stage(repository, "allocation", client=client)

    with repository.database.transaction() as transaction:
        role = transaction.execute("SELECT minimum_quality_value, maximum_quality_value FROM roles WHERE id = 'routing_fast'").fetchone()
        plan = transaction.execute("SELECT targets FROM allocation_plans WHERE role_id = 'routing_fast' ORDER BY created_at DESC LIMIT 1").fetchone()
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
            repository.roles.upsert(transaction, role_id=role_id, requirements=requirements, expected_load={"requests": 1}, criticality=1)
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
        plan_count = transaction.execute("SELECT count(*) AS total FROM allocation_plans WHERE role_id = 'stale_gate'").fetchone()["total"]
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


@pytest.mark.spec("pipeline-orchestration::Allocation persists one combo plan per role")
@pytest.mark.spec("pipeline-orchestration::Oversubscription gate blocks zero-capacity pool")
@pytest.mark.spec("pipeline-orchestration::Inventory precedes scoring")
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
        plan = transaction.execute("SELECT role_id, status, targets, constraint_report FROM allocation_plans").fetchone()
    assert result.exit_code == 0
    assert result.stage_results[0]["details"]["effect"] == "repository_write"
    assert plan["role_id"] == "routing_fast"
    assert plan["status"] == "planned"
    assert len(plan["targets"]) == 1
    assert plan["constraint_report"]["apply"] is True
    assert plan["constraint_report"]["pool_reports"][next(iter(plan["constraint_report"]["pool_reports"]))]["usage"] == pytest.approx(39.6)


@pytest.mark.spec("pipeline-orchestration::Diff is computed without mutating OmniRoute")
@pytest.mark.spec("smart-combo-reviewer::Reviewer output is recorded")
@pytest.mark.spec("smart-combo-reviewer::Applied diff is independent of the reviewer")
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
    dependencies = StageDependencies(repository=repository, omniroute_client=client, config=config, llm_runtime=llm_runtime)

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
    assert any(call[0] == "/v1/chat/completions" for call in client.calls)
    assert not any(call[0] == "/api/combos/test" for call in client.calls)
    assert next(call for call in client.calls if call[0].startswith("/api/combos/"))[3]
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
@pytest.mark.parametrize(
    "quota_update",
    [
        "UPDATE endpoint_access_states SET hard_stop_capable = false",
        "UPDATE endpoint_access_states SET reset_at = now() - interval '1 minute'",
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
    seed_apply_ready_diff(repository, role_id="missing", combo_id="fmo-missing", before=[], after_model_id="free-missing")
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
    present_endpoint = seed_apply_ready_diff(repository, role_id="routing_fast", combo_id="fmo-routing_fast", before=["old-endpoint"], after_model_id="free-present")
    seed_apply_ready_diff(repository, role_id="missing", combo_id="fmo-missing", before=[], after_model_id="free-missing")
    client = PipelineOpsClient()

    result = run_composed_stage(repository, "apply", client=client)

    assert result.exit_code == 0
    assert client.combos["fmo-routing_fast"] == [present_endpoint]
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
        applied = transaction.execute("SELECT count(*) AS total FROM combo_snapshots WHERE phase = 'applied'").fetchone()
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
            LLM_BOOTSTRAP_MODEL_ID="free-bootstrap",
            LLM_BOOTSTRAP_MODEL_CONFIRMED_FREE="true",
        )
    )
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
        adapters=StageAdapters(
            instructor_from_openai=instructor_from_openai,
            openai_client_factory=openai_client_factory,
        ),
    )

    response = runtime.complete(
        site=type("Site", (), {"name": "quota-research-inspector", "model": "paid-static", "prompt_path": None, "max_prompt_chars": 1000, "retries": 1})(),
        context={"prompt": "quota"},
        response_model=QuotaClaimResponse,
    )

    assert response.amount == 1
    assert openai_clients[0].kwargs == {"base_url": "https://omniroute.test/v1", "api_key": "test-key"}
    assert instructor_clients == openai_clients
    assert fake_instructor_client.chat.completions.calls[0]["model"] == "free-bootstrap"


@pytest.mark.spec("llm-runtime::Highest-index confirmed-free model selected")
@pytest.mark.spec("llm-runtime::Falls to next model by index on unavailability")
def test_llm_model_selection_uses_confirmed_free_index_order_and_no_llm_fallback(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    config = build_startup_config(valid_env(DATABASE_URL=postgres_url))
    seed_confirmed_llm_candidate(repository, model_id="free-low", intelligence_index=40)
    seed_confirmed_llm_candidate(repository, model_id="free-high", intelligence_index=90, remaining=0)
    seed_confirmed_llm_candidate(repository, model_id="free-unhealthy", intelligence_index=95, health_status="degraded")

    selected = select_llm_model(repository, config)

    with repository.database.transaction() as transaction:
        combo_count = transaction.execute("SELECT count(*) AS total FROM combo_snapshots").fetchone()["total"]
    assert selected == "free-low"
    assert combo_count == 0

    empty_repository = Repository(Database(postgres_url))
    assert select_llm_model(empty_repository, config) == "free-low"


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
        migration = transaction.execute("SELECT status, threshold_proposal_json FROM artificial_analysis_index_migrations").fetchone()
        threshold = transaction.execute("SELECT role_id, metric, threshold_value, is_active FROM artificial_analysis_threshold_versions").fetchone()
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
        migration_count = transaction.execute("SELECT count(*) AS total FROM artificial_analysis_index_migrations").fetchone()["total"]
        combo_count = transaction.execute("SELECT count(*) AS total FROM combo_snapshots WHERE omniroute_combo_id LIKE 'fmo-%'").fetchone()["total"]
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

    cron_now = datetime.now(timezone.utc).replace(hour=4, minute=0, second=0, microsecond=0)
    cli_result = runtime.run_scheduler_once(cron_now.isoformat())

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
