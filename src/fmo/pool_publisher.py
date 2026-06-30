from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from fmo.idempotency import stable_hash
from fmo.omniroute import OmniRouteClient, OmniRouteVersionGate
from fmo.persistence import Repository

POOL_CONTRACT_VERSION = "fmo-pools/v1"
SHARED_CAPABILITY_ALIASES = {
    "tool_calling": "tool_call",
    "tools": "tool_call",
}
QUALITY_CATEGORY_BY_METRIC = {
    # AICODE-NOTE: OmniRoute resolves these category names through
    # getResolvedTaskFitness(model, category); keep FMO metrics mapped to
    # categories persisted in OmniRoute's model_intelligence table.
    "intelligence_index": "intelligence",
    "coding_index": "coding",
    "agentic_index": "agentic",
}


@dataclass(frozen=True)
class PoolPublishResult:
    generation: str
    payload_hash: str
    status: str
    response: dict[str, Any]


def compose_pool_generation(
    roles: list[dict[str, Any]],
    demand: Mapping[str, float],
    *,
    generation: str | None = None,
) -> dict[str, Any]:
    pools = []
    for role in roles:
        if role.get("role_lifecycle_status") not in {"active", "bootstrap_pending"}:
            continue
        requirements = dict(role.get("requirements") or {})
        min_context_tokens = requirements.get("min_context_tokens") or requirements.get("minimum_context_window")
        if min_context_tokens is None:
            raise ValueError(f"pool {role['id']} missing min_context_tokens")
        pools.append(
            {
                "pool_id": requirements.get("pool_id") or role["id"],
                "combo_id": requirements.get("combo_id") or f"fmo-{role['id']}",
                "demand": {
                    "requests_per_day": float(demand.get(role["id"], 0.0)),
                    "consumers": int(role.get("consumer_count") or 0),
                    "workload_class": requirements.get("workload_class") or "standard",
                },
                "constraints": {
                    "free_only": bool(requirements.get("free_only", True)),
                    "capabilities": _shared_capabilities(requirements.get("capabilities") or []),
                    "min_context_tokens": int(min_context_tokens),
                    "quality_band": _quality_band(role, requirements),
                },
                "tail": {"strategy": "auto", "mode": "fallback", "compatibility": "strict"},
            }
        )
    return {
        "contract_version": POOL_CONTRACT_VERSION,
        "generation": generation or datetime.now(UTC).isoformat(),
        "pools": pools,
    }


def publish_pool_generation(
    repository: Repository,
    client: OmniRouteClient,
    generation: dict[str, Any],
    *,
    run_id: str | None,
    version_gate: OmniRouteVersionGate,
    server_version: str | None = None,
) -> PoolPublishResult:
    version = server_version or str(client.get("/api/version").get("version") or "")
    decision = version_gate.evaluate(version)
    if not decision.can_apply:
        raise ValueError(f"unsupported pool contract {POOL_CONTRACT_VERSION} on OmniRoute {version}")
    payload_hash = stable_hash(generation)
    # AICODE-NOTE: Pool publish idempotency is payload-hash based; generation
    # markers may repeat during retries or operator-triggered replays.
    response = client.put("/api/fmo/pools", generation, idempotency_key=payload_hash)
    status = str(response.get("status") or "acknowledged")
    with repository.database.transaction() as transaction:
        repository.published_generations.upsert(
            transaction,
            generation=str(generation["generation"]),
            payload_hash=payload_hash,
            payload_json=generation,
            status=status,
        )
        repository.audit.record(
            transaction,
            run_id=run_id,
            entity_type="fmo-pools",
            entity_id=str(generation["generation"]),
            action="publish",
            after_json={"payload_hash": payload_hash, "status": status},
            reason_codes=["pool_spec_publish"],
            source_refs=[{"contract_version": POOL_CONTRACT_VERSION, "omniroute_version": version}],
        )
    return PoolPublishResult(
        generation=str(generation["generation"]),
        payload_hash=payload_hash,
        status=status,
        response=response,
    )


def usage_feedback(client: OmniRouteClient) -> dict[str, Any]:
    return client.get("/api/fmo/usage")


def _quality_band(role: dict[str, Any], requirements: dict[str, Any]) -> dict[str, Any]:
    metric = role.get("minimum_quality_metric") or requirements.get("quality_metric") or "intelligence_index"
    minimum = role.get("minimum_quality_value")
    maximum = role.get("maximum_quality_value")
    relax = requirements.get("quality_relax") or {"when": "underfilled", "max_delta": 0}
    return {
        "source": "model_intelligence",
        "metric": "score",
        "category": _quality_category(metric),
        "min": float(minimum) if minimum is not None else 0.0,
        "max": float(maximum) if maximum is not None else 100.0,
        "relax": relax,
    }


def _quality_category(metric: str) -> str:
    return QUALITY_CATEGORY_BY_METRIC.get(metric, metric)


def _shared_capabilities(capabilities: Iterable[Any]) -> list[str]:
    tokens = []
    for capability in capabilities:
        token = str(capability).strip().lower()
        if not token:
            continue
        tokens.append(SHARED_CAPABILITY_ALIASES.get(token, token))
    return sorted(set(tokens))
