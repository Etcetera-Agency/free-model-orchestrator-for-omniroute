from dataclasses import dataclass
from typing import Any


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


def sync_free_registry(payload: dict[str, Any], *, rankings_payload: dict[str, Any] | None = None) -> FreeRegistry:
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
