import hashlib
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any


def utcnow() -> datetime:
    return datetime.now(UTC)


def stable_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def canonical_slug(provider_model_id: str) -> str:
    return provider_model_id.lower().split("/")[-1].replace("_", "-")


def hash_parts(*parts: str) -> str:
    return hashlib.sha256(":".join(parts).encode("utf-8")).hexdigest()


def combo_models_idempotency_key(_combo_id: str, models: Sequence[str]) -> str:
    payload = json.dumps(list(models), separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def provider_model_idempotency_key(provider: str, model_id: str) -> str:
    digest = hash_parts(provider, model_id)
    return f"fmo-provider-model:{digest}"
