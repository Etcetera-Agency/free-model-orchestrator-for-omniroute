from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from fmo.db import MigrationRunner
from fmo.composition import StageAdapters, StageDependencies, build_canonical_stages
from fmo.model_registration import register_new_free_models
from fmo.persistence import Database, Repository
from fmo.pipeline import PipelineRunner
from test_composition import (
    PipelineOpsClient,
    run_composed_stage,
    run_rebalance_stages,
    seed_confirmed_llm_candidate,
    seed_endpoint,
)
from _fixtures import fixture_body


FIXTURE_PROVIDER = fixture_body("omniroute_api_rate_limits")["connections"][0]["provider"]
FIXTURE_CONNECTION_ID = fixture_body("omniroute_api_rate_limits")["connections"][0]["connectionId"]


class RegistrationClient:
    def __init__(self, *, providers=None):
        self.providers = providers or [FIXTURE_PROVIDER]
        self.rate_limits_body = deepcopy(fixture_body("omniroute_api_rate_limits"))
        for connection in self.rate_limits_body["connections"]:
            connection["enabled"] = connection["provider"] in self.providers
            connection["active"] = connection["provider"] in self.providers
        self.posts = []
        self.deleted_paths = []
        self.patch_paths = []

    def get(self, path):
        if path == "/api/rate-limits":
            return self.rate_limits_body
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
        self.providers_body = {
            "connections": [
                {
                    "id": FIXTURE_CONNECTION_ID,
                    "provider": FIXTURE_PROVIDER,
                    "enabled": True,
                    "isActive": True,
                    "upstream_account_id": FIXTURE_CONNECTION_ID,
                    "status": "confirmed",
                }
            ]
        }
        self.rate_limits_body = {
            "connections": [
                {
                    "connectionId": FIXTURE_CONNECTION_ID,
                    "provider": FIXTURE_PROVIDER,
                    "enabled": True,
                    "active": True,
                    "remaining": 100,
                }
            ]
        }
        self.quota_body.setdefault("providers", []).append(
            {
                "provider": FIXTURE_PROVIDER,
                "connectionId": FIXTURE_CONNECTION_ID,
                "quotaTotal": 200_000,
                "quotaUsed": 80_000,
                "quotaWindow": "day",
                "resetAt": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
            }
        )

    def get(self, path):
        if path == "/v1/models":
            body = deepcopy(fixture_body("omniroute_v1_models"))
            body["data"].extend(
                {"id": model_id, "owned_by": FIXTURE_PROVIDER}
                for model_id in sorted(self.provider_models)
            )
            return body
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
        _payload((FIXTURE_PROVIDER, "new-free", "free")),
    )

    assert report.registered == [(FIXTURE_PROVIDER, "new-free")]
    assert client.posts[0][0] == "/api/provider-models"
    assert client.posts[0][1]["provider"] == FIXTURE_PROVIDER
    assert client.posts[0][1]["modelId"] == "new-free"
    assert client.posts[0][1]["source"] == "fmo"
    assert client.posts[0][3].startswith("fmo-provider-model:")


@pytest.mark.spec("model-registration::Registration is idempotent and additive")
def test_existing_endpoint_is_not_registered_again(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    seed_endpoint(repository, model_id="known-free", provider_id=FIXTURE_PROVIDER, connection_id=f"conn-{FIXTURE_PROVIDER}")
    client = RegistrationClient()

    report = register_new_free_models(
        repository,
        client,
        _payload((FIXTURE_PROVIDER, "known-free", "free")),
    )

    assert report.skipped_existing == [(FIXTURE_PROVIDER, "known-free")]
    assert client.posts == []
    assert client.deleted_paths == []
    assert client.patch_paths == []


@pytest.mark.spec("model-registration::Model outside our connections is skipped")
def test_new_free_model_outside_connections_is_reported_and_skipped(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    client = RegistrationClient(providers=[FIXTURE_PROVIDER])

    report = register_new_free_models(
        repository,
        client,
        _payload(("not-in-recorded-rate-limits", "outside-free", "free")),
    )

    assert report.unreachable == [("not-in-recorded-rate-limits", "outside-free")]
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
        _payload((FIXTURE_PROVIDER, "paid-model", "paid"), (FIXTURE_PROVIDER, "zero-cost", "0-cost")),
    )

    assert report.registered == [(FIXTURE_PROVIDER, "zero-cost")]
    assert [post[1]["modelId"] for post in client.posts] == ["zero-cost"]
    assert client.deleted_paths == []
    assert client.patch_paths == []


def test_registered_model_flows_to_existing_combo_rebalance(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    old = seed_confirmed_llm_candidate(
        repository,
        model_id="old-free",
        intelligence_index=70,
        provider_id=FIXTURE_PROVIDER,
        connection_id=FIXTURE_CONNECTION_ID,
        omniroute_instance_id="default",
    )
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
    registry_payload = _payload((FIXTURE_PROVIDER, "old-free", "free"), (FIXTURE_PROVIDER, "new-free", "free"))

    discovery = _run_free_candidate_full(repository, client, registry_payload)
    matching = run_composed_stage(repository, "model-matching", client=client)
    _record_aa_metric(repository, model_id="new-free", intelligence_index=70)
    _add_live_quota_rows_for_provider(repository, client, provider_id=FIXTURE_PROVIDER)
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
    assert "new-free" in {payload["modelId"] for payload, _key in client.registered_payloads}
    assert new_endpoint_ids
    assert [result.exit_code for result in rebalance_results] == [0] * 9, rebalance_results[-1].stage_results[0]["reason"]
    combo_members = set(client.combos["fmo-routing_fast"])
    assert combo_members & old_endpoint_ids
    assert not client.deleted_paths


def _add_live_quota_rows_for_provider(repository, client, *, provider_id):
    with repository.database.transaction() as transaction:
        rows = transaction.execute(
            """
            SELECT DISTINCT pa.omniroute_connection_id
            FROM provider_accounts pa
            JOIN providers p ON p.id = pa.provider_id
            WHERE p.omniroute_provider_id = %(provider_id)s
            """,
            {"provider_id": provider_id},
        ).fetchall()
    for row in rows:
        client.quota_body.setdefault("providers", []).append(
            {
                "provider": provider_id,
                "connectionId": row["omniroute_connection_id"],
                "quotaTotal": 200_000,
                "quotaUsed": 80_000,
                "quotaWindow": "day",
                "resetAt": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
            }
        )
