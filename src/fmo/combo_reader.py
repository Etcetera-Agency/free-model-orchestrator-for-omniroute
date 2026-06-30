from __future__ import annotations

from typing import Any


def read_current_combos(client: Any | None) -> dict[str, list[Any]]:
    return {combo_id: list(state["models"]) for combo_id, state in read_current_combo_states(client).items()}


def read_current_combo_states(client: Any | None) -> dict[str, dict[str, Any]]:
    if client is None or not hasattr(client, "get"):
        return {}
    payload = client.get("/api/combos")
    combos = payload.get("combos", []) if isinstance(payload, dict) else []
    current: dict[str, dict[str, Any]] = {}
    for combo in combos:
        if not isinstance(combo, dict):
            continue
        combo_key = _live_combo_key(combo)
        if combo_key is None:
            continue
        current[combo_key] = {
            "write_id": str(combo.get("id") or combo_key),
            "models": [_normalize_combo_member(model) for model in combo.get("models", [])],
        }
    return current


def _live_combo_key(combo: dict[str, Any]) -> str | None:
    # AICODE-NOTE: Read-only combo lookup remains for diagnostics/profile normalization;
    # FMO no longer writes combo rows after allocation/apply removal.
    for field in ("name", "id"):
        value = str(combo.get(field) or "")
        if value.startswith("fmo-"):
            return value
    return None


def _normalize_combo_member(member: Any) -> Any:
    if not isinstance(member, dict):
        return member
    provider = member.get("provider")
    model = member.get("model")
    if provider and model:
        return f"{provider}/{model}"
    return member.get("providerModelId") or member.get("provider_model_id") or member
