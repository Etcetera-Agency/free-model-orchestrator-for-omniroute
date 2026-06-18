from typing import Any

import httpx

from fmo.candidates import FreeCandidate, build_free_candidates
from fmo.external_metadata import ExternalMetadataError


MODELS_DEV_API_URL = "https://models.dev/api.json"


def fetch_models_dev_catalog(*, client=None, url: str = MODELS_DEV_API_URL, timeout: float = 30.0) -> dict[str, Any]:
    http_client = client or httpx
    try:
        response = http_client.get(url, timeout=timeout)
    except Exception as exc:
        raise ExternalMetadataError("models_dev", "network_error") from exc
    if response.status_code != 200:
        raise ExternalMetadataError("models_dev", "http_error", response.status_code)
    try:
        payload = response.json()
    except Exception as exc:
        raise ExternalMetadataError("models_dev", "invalid_json") from exc
    return _normalize_catalog(payload)


def _normalize_catalog(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ExternalMetadataError("models_dev", "invalid_payload")
    # An explicitly injected payload keeps the canonical `{"providers": {...}}`
    # wrapper; the live `https://models.dev/api.json` body is keyed by provider
    # id at the top level with no wrapper. Accept both, reject anything that is
    # not a provider-keyed object (e.g. an error body like `{"error": ...}`).
    if isinstance(payload.get("providers"), dict):
        providers = payload["providers"]
    elif "providers" in payload:
        raise ExternalMetadataError("models_dev", "invalid_payload")
    else:
        providers = payload
    if not _is_provider_map(providers):
        raise ExternalMetadataError("models_dev", "invalid_payload")
    return {"providers": providers}


def _is_provider_map(providers: Any) -> bool:
    return isinstance(providers, dict) and any(isinstance(provider, dict) for provider in providers.values())


def sync_models_dev_candidates(*, client=None, url: str = MODELS_DEV_API_URL, timeout: float = 30.0) -> dict[tuple[str, str], FreeCandidate]:
    return build_free_candidates(fetch_models_dev_catalog(client=client, url=url, timeout=timeout))
