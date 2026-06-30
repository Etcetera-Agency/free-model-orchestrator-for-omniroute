import json
from pathlib import Path
from typing import Any

import pytest

from fmo.composition import build_publisher_stages
from fmo.composition_stages import StageDependencies
from fmo.db import MigrationRunner
from fmo.idempotency import stable_hash
from fmo.omniroute import OmniRouteVersionGate
from fmo.persistence import Database, Repository
from fmo.pool_publisher import compose_pool_generation, publish_pool_generation, usage_feedback

GOLDEN_POOL_GENERATION = Path("reference/fixtures/fmo-pools-v1-generation.json")
OMNIROUTE_POOL_GENERATION = Path("../OmniRoute/tests/fixtures/fmo/fmo-pools-v1.golden.json")
CANONICAL_GENERATED_AT = "2026-06-29T00:00:00.000Z"
SHARED_CAPABILITY_TOKENS = {
    "api:openai",
    "chat",
    "developer_role",
    "protocol:openai",
    "thinking",
    "tool_call",
}
OMNIROUTE_QUALITY_CATEGORIES = {"agentic", "coding", "intelligence"}
CONTRACT_WORKLOAD_CLASSES = {"light", "chat", "reasoning", "tools"}


@pytest.fixture()
def repository(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    return Repository(Database(postgres_url))


@pytest.mark.spec("pool-spec-publisher::Compose and publish from inventory")
@pytest.mark.spec("pool-spec-publisher::Never writes combos")
@pytest.mark.spec("pool-spec-publisher::Demand from forecast, consumers from inventory")
@pytest.mark.spec("pool-spec-publisher::No capacity computation")
@pytest.mark.spec("demand-forecast::Band is declared, not computed")
@pytest.mark.spec("demand-forecast::Relax is delegated, not applied in FMO")
@pytest.mark.spec("pool-spec-publisher::Emitted payload matches the shared fixture")
def test_compose_pool_generation_uses_role_policy_and_forecast_only():
    roles = [
        {
            "id": "routing_fast",
            "role_lifecycle_status": "active",
            "requirements": {
                "pool_id": "pool-fast",
                "combo_id": "combo-fast",
                "workload_class": "reasoning",
                "capabilities": ["chat", "tools", "thinking", "api:openai"],
                "min_context_tokens": 32768,
                "quality_relax": {"when": "underfilled", "max_delta": 12},
            },
            "minimum_quality_metric": "coding_index",
            "minimum_quality_value": 55,
            "maximum_quality_value": 85,
            "consumer_count": 4,
        }
    ]

    generation = compose_pool_generation(
        roles,
        {"routing_fast": 1000},
        generation="gen-1",
        generated_at=CANONICAL_GENERATED_AT,
    )

    assert generation == _golden_generation(generation="gen-1")
    _assert_canonical_pool_generation(generation)
    assert set(generation["pools"][0]["constraints"]["capabilities"]).issubset(SHARED_CAPABILITY_TOKENS)
    assert generation["pools"][0]["constraints"]["quality_band"]["category"] in OMNIROUTE_QUALITY_CATEGORIES
    assert "models" not in generation["pools"][0]
    assert "capacity" not in str(generation)


@pytest.mark.spec("pool-spec-publisher::Shared fixture is byte-identical across repos")
def test_shared_golden_fixture_matches_deterministic_composition():
    roles = [
        {
            "id": "routing_fast",
            "role_lifecycle_status": "active",
            "requirements": {
                "pool_id": "pool-fast",
                "combo_id": "combo-fast",
                "workload_class": "reasoning",
                "capabilities": ["tools", "api:openai", "thinking", "chat"],
                "min_context_tokens": 32768,
                "quality_relax": {"max_delta": 12, "when": "underfilled"},
            },
            "minimum_quality_metric": "coding_index",
            "minimum_quality_value": 55,
            "maximum_quality_value": 85,
            "consumer_count": 4,
        }
    ]

    generation = compose_pool_generation(
        roles,
        {"routing_fast": 1000},
        generation="gen-001",
        generated_at=CANONICAL_GENERATED_AT,
    )

    assert generation == _golden_generation()
    _assert_canonical_pool_generation(generation)
    assert GOLDEN_POOL_GENERATION.read_text(encoding="utf-8") == OMNIROUTE_POOL_GENERATION.read_text(encoding="utf-8")
    assert type(generation["pools"][0]["demand"]["requests_per_day"]) is int
    assert type(generation["pools"][0]["demand"]["consumers"]) is int


def test_capability_aliases_use_omniroute_matching_tokens():
    generation = compose_pool_generation(
        [
            {
                "id": "routing_fast",
                "role_lifecycle_status": "active",
                "requirements": {
                    "capabilities": ["tools", "tool_calling", "tool_call", "api:openai", "thinking"],
                    "min_context_tokens": 8192,
                },
            }
        ],
        {"routing_fast": 1},
        generation="gen-1",
    )

    assert generation["pools"][0]["constraints"]["capabilities"] == [
        "api:openai",
        "thinking",
        "tool_call",
    ]


def _golden_generation(*, generation: str = "gen-001") -> dict[str, Any]:
    payload = json.loads(GOLDEN_POOL_GENERATION.read_text(encoding="utf-8"))
    payload["generation"] = generation
    return payload


def _assert_canonical_pool_generation(generation: dict[str, Any]) -> None:
    assert set(generation) == {"contract_version", "generation", "generated_at", "pools"}
    assert generation["contract_version"] == "fmo-pools/v1"
    assert isinstance(generation["pools"], list)
    assert generation["pools"]
    for pool in generation["pools"]:
        assert set(pool) == {"pool_id", "combo_id", "demand", "constraints", "tail"}
        assert set(pool["demand"]) == {"requests_per_day", "consumers", "workload_class"}
        assert set(pool["constraints"]) == {
            "free_only",
            "capabilities",
            "min_context_tokens",
            "quality_band",
        }
        assert type(pool["constraints"]["min_context_tokens"]) is int
        assert set(pool["constraints"]["quality_band"]) == {
            "source",
            "metric",
            "category",
            "min",
            "max",
            "relax",
        }
        assert set(pool["constraints"]["quality_band"]["relax"]) == {"max_delta", "when"}
        assert 0 <= pool["constraints"]["quality_band"]["min"] <= pool["constraints"]["quality_band"]["max"] <= 1
        assert set(pool["tail"]) == {"strategy", "mode", "compatibility"}
        assert "members" not in pool["tail"]


def _generation(generation: str, *, requests: float) -> dict:
    return {
        "contract_version": "fmo-pools/v1",
        "generation": generation,
        "generated_at": CANONICAL_GENERATED_AT,
        "pools": [
            {
                "pool_id": "pool-fast",
                "combo_id": "combo-fast",
                "demand": {"requests_per_day": requests, "consumers": 1, "workload_class": "standard"},
                "constraints": {
                    "free_only": True,
                    "capabilities": ["chat"],
                    "min_context_tokens": 8192,
                    "quality_band": {
                        "source": "model_intelligence",
                        "metric": "score",
                        "category": "intelligence",
                        "min": 50,
                        "max": 90,
                        "relax": {"when": "underfilled", "max_delta": 10},
                    },
                },
                "tail": {"strategy": "auto", "mode": "fallback", "compatibility": "strict"},
            }
        ],
    }


@pytest.mark.spec("pool-spec-publisher::Missing context bound fails closed")
def test_compose_pool_generation_rejects_missing_context_bound():
    roles = [{"id": "routing_fast", "role_lifecycle_status": "active", "requirements": {}}]

    with pytest.raises(ValueError, match="missing min_context_tokens"):
        compose_pool_generation(roles, {"routing_fast": 1}, generation="gen-1")


@pytest.mark.spec("pool-spec-publisher::Quality band emitted on the normalized scale")
@pytest.mark.spec("pool-spec-publisher::workload_class stays in the contract vocabulary")
def test_compose_pool_generation_normalizes_quality_band_and_workload_class():
    generation = compose_pool_generation(
        [
            {
                "id": "routing_fast",
                "role_lifecycle_status": "active",
                "requirements": {
                    "workload_class": "standard",
                    "capabilities": ["chat"],
                    "min_context_tokens": 8192,
                },
                "minimum_quality_value": 55,
                "maximum_quality_value": 85,
            },
            {
                "id": "routing_tools",
                "role_lifecycle_status": "active",
                "requirements": {
                    "workload_class": "unknown",
                    "capabilities": ["tools"],
                    "min_context_tokens": 8192,
                },
                "minimum_quality_value": 0.25,
                "maximum_quality_value": 0.75,
            },
        ],
        {"routing_fast": 5, "routing_tools": 7},
        generation="gen-1",
    )

    fast_pool, tools_pool = generation["pools"]
    assert fast_pool["constraints"]["quality_band"]["min"] == 0.55
    assert fast_pool["constraints"]["quality_band"]["max"] == 0.85
    assert fast_pool["demand"]["workload_class"] == "chat"
    assert tools_pool["constraints"]["quality_band"]["min"] == 0.25
    assert tools_pool["constraints"]["quality_band"]["max"] == 0.75
    assert tools_pool["demand"]["workload_class"] == "chat"
    assert {pool["demand"]["workload_class"] for pool in generation["pools"]}.issubset(CONTRACT_WORKLOAD_CLASSES)


@pytest.mark.spec("pool-spec-publisher::Quality band emitted on the normalized scale")
def test_compose_pool_generation_rejects_unmappable_quality_band():
    roles = [
        {
            "id": "routing_fast",
            "role_lifecycle_status": "active",
            "requirements": {"capabilities": ["chat"], "min_context_tokens": 8192},
            "minimum_quality_value": 55,
            "maximum_quality_value": 150,
        }
    ]

    with pytest.raises(ValueError, match=r"quality_band max 150.0 cannot be normalized"):
        compose_pool_generation(roles, {"routing_fast": 1}, generation="gen-1")


@pytest.mark.spec("pool-spec-publisher::Retry is idempotent")
@pytest.mark.spec("pool-spec-publisher::Changed payload gets new idempotency key")
@pytest.mark.spec("pool-spec-publisher::Idempotency stays payload-hash based")
@pytest.mark.spec("omniroute-client::Supported version publishes")
def test_publish_pool_generation_uses_payload_hash_idempotency(repository):
    client = FakePoolClient(version="1.4.0")
    gate = OmniRouteVersionGate({"1.4.0"})
    generation = _generation("gen-1", requests=5)
    changed = _generation("gen-1", requests=6)

    first = publish_pool_generation(repository, client, generation, run_id=None, version_gate=gate)
    second = publish_pool_generation(repository, client, generation, run_id=None, version_gate=gate)
    third = publish_pool_generation(repository, client, changed, run_id=None, version_gate=gate)

    assert first.payload_hash == stable_hash(generation)
    assert second.payload_hash == first.payload_hash
    assert third.payload_hash == stable_hash(changed)
    assert third.payload_hash != first.payload_hash
    assert [request["path"] for request in client.requests] == [
        "/api/version",
        "/api/fmo/pools",
        "/api/version",
        "/api/fmo/pools",
        "/api/version",
        "/api/fmo/pools",
    ]
    assert client.requests[1]["idempotency_key"] == first.payload_hash
    assert client.requests[3]["idempotency_key"] == first.payload_hash
    assert client.requests[5]["idempotency_key"] == third.payload_hash
    assert client.requests[1]["idempotency_key"] != generation["generation"]
    with repository.database.transaction() as transaction:
        same_payload = repository.published_generations.get(transaction, "gen-1", first.payload_hash)
        changed_payload = repository.published_generations.get(transaction, "gen-1", third.payload_hash)
    assert same_payload is not None
    assert changed_payload is not None


@pytest.mark.spec("omniroute-client::Unsupported contract version refuses publish")
def test_publish_pool_generation_rejects_unsupported_contract(repository):
    client = FakePoolClient(version="9.9.9")
    gate = OmniRouteVersionGate({"1.4.0"})

    with pytest.raises(ValueError, match="unsupported pool contract"):
        publish_pool_generation(repository, client, _generation("gen-1", requests=5), run_id=None, version_gate=gate)

    assert [request["path"] for request in client.requests] == ["/api/version"]


@pytest.mark.spec("pool-spec-publisher::Feedback adjusts next demand")
def test_usage_feedback_reads_fmo_usage_endpoint():
    client = FakePoolClient(version="1.4.0", usage={"pools": [{"pool_id": "pool-fast", "requests": 9}]})

    assert usage_feedback(client) == {"pools": [{"pool_id": "pool-fast", "requests": 9}]}
    assert client.requests == [{"method": "GET", "path": "/api/fmo/usage"}]


def test_build_publisher_stages_keeps_pipeline_runner_contract():
    stages = build_publisher_stages(dependencies=StageDependencies(repository=None, omniroute_client=None))

    assert [stage.name for stage in stages] == [
        "hermes-inventory",
        "role-lifecycle",
        "demand-forecast",
        "compose",
        "publish",
        "usage-feedback",
    ]


class FakePoolClient:
    def __init__(self, *, version: str, usage: dict | None = None):
        self.version = version
        self.usage = usage or {"pools": []}
        self.requests: list[dict[str, Any]] = []

    def get(self, path: str) -> dict[str, Any]:
        self.requests.append({"method": "GET", "path": path})
        if path == "/api/version":
            return {"version": self.version}
        if path == "/api/fmo/usage":
            return self.usage
        raise AssertionError(path)

    def put(self, path: str, payload: dict[str, Any], *, idempotency_key: str | None = None) -> dict[str, str]:
        self.requests.append({"method": "PUT", "path": path, "payload": payload, "idempotency_key": idempotency_key})
        if path != "/api/fmo/pools":
            raise AssertionError(path)
        return {"status": "accepted"}
