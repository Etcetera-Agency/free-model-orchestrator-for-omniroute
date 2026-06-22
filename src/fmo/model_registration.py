from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from fmo.persistence import Repository


@dataclass(frozen=True)
class RegistrationReport:
    registered: list[tuple[str, str]]
    skipped_existing: list[tuple[str, str]]
    unreachable: list[tuple[str, str]]

    @property
    def changed(self) -> bool:
        return bool(self.registered)


def register_new_free_models(
    repository: Repository,
    client: Any,
    free_models_payload: dict[str, Any],
) -> RegistrationReport:
    reachable = _reachable_providers(client)
    existing = _existing_endpoint_keys(repository)
    registered: list[tuple[str, str]] = []
    skipped_existing: list[tuple[str, str]] = []
    unreachable: list[tuple[str, str]] = []

    for model in _confirmed_free_models(free_models_payload):
        key = (model["provider"], model["modelId"])
        if key[0] not in reachable:
            unreachable.append(key)
            continue
        if key in existing:
            skipped_existing.append(key)
            continue
        # AICODE-NOTE: this is the only OmniRoute write outside fmo combo
        # mutation; it is additive, free-only, and provider/connection-scoped.
        client.post(
            "/api/provider-models",
            {
                "provider": model["provider"],
                "modelId": model["modelId"],
                "modelName": model.get("displayName"),
                "source": "fmo",
                "apiFormat": model.get("apiFormat"),
                "supportedEndpoints": model.get("supportedEndpoints"),
                "targetFormat": model.get("targetFormat"),
            },
            idempotency_key=_idempotency_key(*key),
        )
        registered.append(key)
    return RegistrationReport(
        registered=registered,
        skipped_existing=skipped_existing,
        unreachable=unreachable,
    )


def _confirmed_free_models(payload: dict[str, Any]) -> list[dict[str, Any]]:
    models = payload.get("models", [])
    if not isinstance(models, list):
        return []
    return [
        item
        for item in models
        if isinstance(item, dict)
        and item.get("provider")
        and item.get("modelId")
        and _free_type(item.get("freeType"))
    ]


def _free_type(value: Any) -> bool:
    return str(value or "").lower() in {"free", "zero_cost", "0-cost", "free_provider"}


def _reachable_providers(client: Any) -> set[str]:
    try:
        payload = client.get("/api/rate-limits")
    except Exception:
        return set()
    connections = payload.get("connections") if isinstance(payload, dict) else None
    if not isinstance(connections, list):
        return set()
    return {
        str(connection["provider"])
        for connection in connections
        if isinstance(connection, dict) and connection.get("provider") and connection.get("enabled", True)
    }


def _existing_endpoint_keys(repository: Repository) -> set[tuple[str, str]]:
    with repository.database.transaction() as transaction:
        rows = transaction.execute(
            """
            SELECT p.omniroute_provider_id, pe.provider_model_id
            FROM provider_endpoints pe
            JOIN provider_accounts pa ON pa.id = pe.provider_account_id
            JOIN providers p ON p.id = pa.provider_id
            """
        ).fetchall()
    return {(str(row["omniroute_provider_id"]), str(row["provider_model_id"])) for row in rows}


def _idempotency_key(provider: str, model_id: str) -> str:
    digest = hashlib.sha256(f"{provider}:{model_id}".encode("utf-8")).hexdigest()
    return f"fmo-provider-model:{digest}"
