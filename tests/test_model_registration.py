from pathlib import Path
from types import SimpleNamespace

import pytest

from fmo.db import MigrationRunner
from fmo.composition import StageAdapters, StageDependencies, build_canonical_stages
from fmo.model_registration import register_new_free_models
from fmo.persistence import Database, Repository
from fmo.pipeline import PipelineRunner
from tests.test_composition import (
    PipelineOpsClient,
    run_composed_stage,
    run_rebalance_stages,
    seed_confirmed_llm_candidate,
    seed_endpoint,
)


class RegistrationClient:
    def __init__(self, *, providers=None):
        self.providers = providers or ["provider-a"]
        self.posts = []
        self.deleted_paths = []
        self.patch_paths = []

    def get(self, path):
        if path == "/api/rate-limits":
            return {
                "connections": [
                    {"connectionId": f"conn-{provider}", "provider": provider, "enabled": True}
                    for provider in self.providers
                ]
            }
        raise AssertionError(f"unexpected GET {path}")

    def post(self, path, payload, headers=None, idempotency_key=None):
        self.posts.append((path, payload, headers, idempotency_key))
        return {"ok": True}

    def patch(self, path, payload):
        self.patch_paths.append(path)
        raise AssertionError(f"unexpected PATCH {path}")

    def delete(self, path):
        self.deleted_paths.append(path)
        raise AssertionError(f"unexpected DELETE {path}")


class RegistrationFlowClient(PipelineOpsClient):
    def __init__(self):
        super().__init__()
        self.provider_models = {"old-free"}
        self.registered_payloads = []
        self.combos = {}

    def get(self, path):
        if path == "/v1/models":
            return {
                "data": [
                    {"id": model_id, "owned_by": "provider-a"}
                    for model_id in sorted(self.provider_models)
                ]
            }
        return super().get(path)

    def post(self, path, payload, headers=None, idempotency_key=None):
        if path == "/api/provider-models":
            self.registered_payloads.append((payload, idempotency_key))
            self.provider_models.add(payload["modelId"])
            return {"ok": True}
        return super().post(path, payload, headers=headers, idempotency_key=idempotency_key)


def _payload(*models):
    return {
        "models": [
            {
                "provider": provider,
                "modelId": model_id,
                "displayName": model_id.title(),
                "freeType": free_type,
            }
            for provider, model_id, free_type in models
        ]
    }


def _run_free_candidate_full(repository, client, registry_payload):
    dependencies = StageDependencies(repository=repository, omniroute_client=client)
    adapters = StageAdapters(
        registry_sync=lambda _client: SimpleNamespace(
            free_models_payload=registry_payload,
            rankings_payload={"providers": []},
            model_count=len(registry_payload["models"]),
            drift=[],
            errors=[],
        )
    )
    stage = next(
        stage
        for stage in build_canonical_stages(dependencies=dependencies, adapters=adapters)
        if stage.name == "free-candidate-discovery"
    )
    return PipelineRunner(repository, stages=[stage], config={"command": "full"}).run(trigger="full", run_type="full")


def _record_aa_metric(repository, *, model_id, intelligence_index):
    with repository.database.transaction() as transaction:
        row = transaction.execute(
            """
            SELECT canonical_model_id
            FROM provider_endpoints
            WHERE provider_model_id = %(model_id)s
            """,
            {"model_id": model_id},
        ).fetchone()
        transaction.execute(
            """
            INSERT INTO artificial_analysis_model_metrics (
              canonical_model_id, intelligence_index, index_version,
              source_payload_hash, stale_after
            )
            VALUES (
              %(model_id)s, %(index)s, '4.1', %(hash)s, now() + interval '1 day'
            )
            """,
            {
                "model_id": row["canonical_model_id"],
                "index": intelligence_index,
                "hash": f"{model_id}:aa",
            },
        )


@pytest.mark.spec("model-registration::New free model under a connection is registered")
def test_new_free_model_under_connection_is_registered(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    client = RegistrationClient()

    report = register_new_free_models(
        repository,
        client,
        _payload(("provider-a", "new-free", "free")),
    )

    assert report.registered == [("provider-a", "new-free")]
    assert client.posts[0][0] == "/api/provider-models"
    assert client.posts[0][1]["provider"] == "provider-a"
    assert client.posts[0][1]["modelId"] == "new-free"
    assert client.posts[0][1]["source"] == "fmo"
    assert client.posts[0][3].startswith("fmo-provider-model:")


@pytest.mark.spec("model-registration::Registration is idempotent and additive")
def test_existing_endpoint_is_not_registered_again(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    seed_endpoint(repository, model_id="known-free")
    client = RegistrationClient()

    report = register_new_free_models(
        repository,
        client,
        _payload(("provider-a", "known-free", "free")),
    )

    assert report.skipped_existing == [("provider-a", "known-free")]
    assert client.posts == []
    assert client.deleted_paths == []
    assert client.patch_paths == []


@pytest.mark.spec("model-registration::Model outside our connections is skipped")
def test_new_free_model_outside_connections_is_reported_and_skipped(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    client = RegistrationClient(providers=["provider-a"])

    report = register_new_free_models(
        repository,
        client,
        _payload(("provider-b", "outside-free", "free")),
    )

    assert report.unreachable == [("provider-b", "outside-free")]
    assert client.posts == []
    assert client.deleted_paths == []


@pytest.mark.spec("system-architecture::Registration is the only added write")
@pytest.mark.spec("model-registration::Registration is idempotent and additive")
def test_registration_is_additive_and_free_only(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    client = RegistrationClient()

    report = register_new_free_models(
        repository,
        client,
        _payload(("provider-a", "paid-model", "paid"), ("provider-a", "zero-cost", "0-cost")),
    )

    assert report.registered == [("provider-a", "zero-cost")]
    assert [post[1]["modelId"] for post in client.posts] == ["zero-cost"]
    assert client.deleted_paths == []
    assert client.patch_paths == []


def test_registered_model_flows_to_existing_combo_rebalance(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    old = seed_confirmed_llm_candidate(repository, model_id="old-free", intelligence_index=70)
    with repository.database.transaction() as transaction:
        repository.roles.upsert(
            transaction,
            role_id="routing_fast",
            requirements={"capabilities": []},
            expected_load={"requests": 1},
            criticality=1,
        )
    client = RegistrationFlowClient()
    client.combos = {"fmo-routing_fast": [str(old["id"])]}
    registry_payload = _payload(("provider-a", "old-free", "free"), ("provider-a", "new-free", "free"))

    discovery = _run_free_candidate_full(repository, client, registry_payload)
    matching = run_composed_stage(repository, "model-matching", client=client)
    _record_aa_metric(repository, model_id="new-free", intelligence_index=70)
    rebalance_results = run_rebalance_stages(repository, client)

    with repository.database.transaction() as transaction:
        old_endpoint_ids = {
            str(row["id"])
            for row in transaction.execute(
                "SELECT id FROM provider_endpoints WHERE provider_model_id = 'old-free'"
            ).fetchall()
        }
        new_endpoint_ids = {
            str(row["id"])
            for row in transaction.execute(
                "SELECT id FROM provider_endpoints WHERE provider_model_id = 'new-free'"
            ).fetchall()
        }
    assert discovery.exit_code == 0
    assert matching.exit_code == 0
    assert client.registered_payloads[0][0]["modelId"] == "new-free"
    assert new_endpoint_ids
    assert [result.exit_code for result in rebalance_results] == [0] * 9
    combo_members = set(client.combos["fmo-routing_fast"])
    assert combo_members & old_endpoint_ids
    assert combo_members & new_endpoint_ids
    assert not client.deleted_paths
