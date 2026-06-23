from dataclasses import dataclass
from typing import Any

from fmo.omniroute import OmniRouteRequestError
from fmo.persistence import Repository

FREE_MODEL_FIELDS = {
    "provider",
    "modelId",
    "displayName",
    "monthlyTokens",
    "creditTokens",
    "freeType",
    "poolKey",
    "tos",
    "authType",
}
REQUIRED_FREE_MODEL_FIELDS = {"provider", "modelId", "freeType"}


@dataclass(frozen=True)
class RegistryModel:
    provider_id: str
    model_id: str
    display_name: str | None
    free_type: str | None
    pool_key: str


@dataclass(frozen=True)
class FreeRegistry:
    models: dict[tuple[str, str | None], RegistryModel]
    pool_budgets: dict[str, float]


@dataclass(frozen=True)
class RegistryFetchError(Exception):
    source: str
    reason: str
    status_code: int | None = None


@dataclass(frozen=True)
class FreeRegistrySyncOutcome:
    registry: FreeRegistry
    free_models_payload: dict[str, Any]
    rankings_payload: dict[str, Any]
    model_count: int
    drift: list[tuple[str, str, str]]
    errors: list[str]


def sync_free_registry(payload: dict[str, Any], *, rankings_payload: dict[str, Any] | None = None) -> FreeRegistry:  # noqa: ARG001 - reserved interface param
    models: dict[tuple[str, str | None], RegistryModel] = {}
    pool_budgets: dict[str, float] = {}
    for item in payload.get("models", []):
        if item.get("authType") == "web_cookie":
            continue
        provider_id = item["provider"]
        model_id = item["modelId"]
        pool_key = item.get("poolKey") or f"{provider_id}:{model_id}"
        budget = float(item.get("monthlyTokens") or item.get("creditTokens") or 0)
        pool_budgets[pool_key] = max(pool_budgets.get(pool_key, 0), budget)
        models[(provider_id, model_id)] = RegistryModel(
            provider_id=provider_id,
            model_id=model_id,
            display_name=item.get("displayName"),
            free_type=item.get("freeType"),
            pool_key=pool_key,
        )
    return FreeRegistry(models=models, pool_budgets=pool_budgets)


def sync_live_free_registry(client: Any) -> FreeRegistrySyncOutcome:
    free_models_payload = _client_get(client, "/api/free-models")
    rankings_payload = _client_get(client, "/api/free-provider-rankings")
    drift = validate_free_registry_payload(free_models_payload)
    registry = sync_free_registry(free_models_payload, rankings_payload=rankings_payload)
    return FreeRegistrySyncOutcome(
        registry=registry,
        free_models_payload=free_models_payload,
        rankings_payload=rankings_payload,
        model_count=len(free_models_payload.get("models", [])),
        drift=drift,
        errors=[],
    )


def validate_free_registry_payload(payload: dict[str, Any]) -> list[tuple[str, str, str]]:
    models = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(models, list):
        return [("models", "missing_field", "models")]

    drift = []
    for index, item in enumerate(models):
        path = f"models[{index}]"
        if not isinstance(item, dict):
            drift.append((path, "invalid_entry", type(item).__name__))
            continue
        for field in sorted(REQUIRED_FREE_MODEL_FIELDS - item.keys()):
            drift.append((path, "missing_field", field))
        for field in sorted(item.keys() - FREE_MODEL_FIELDS):
            drift.append((path, "unknown_field", field))
    return drift


def persist_free_registry_outcome(repository: Repository, outcome: FreeRegistrySyncOutcome) -> str:
    with repository.database.transaction() as transaction:
        snapshot = repository.free_registry.store_outcome(transaction, outcome=outcome)
    return str(snapshot["id"])


def _client_get(client: Any, path: str) -> dict[str, Any]:
    try:
        payload = client.get(path)
    except OmniRouteRequestError as exc:
        raise RegistryFetchError("omniroute_free_registry", "http_error", exc.status_code) from exc
    except Exception as exc:
        raise RegistryFetchError("omniroute_free_registry", "network_error") from exc
    if not isinstance(payload, dict):
        raise RegistryFetchError("omniroute_free_registry", "invalid_payload")
    return payload
