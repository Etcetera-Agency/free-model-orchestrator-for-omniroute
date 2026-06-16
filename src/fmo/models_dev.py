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
    if not isinstance(payload, dict) or not isinstance(payload.get("providers"), dict):
        raise ExternalMetadataError("models_dev", "invalid_payload")
    return payload


def sync_models_dev_candidates(*, client=None, url: str = MODELS_DEV_API_URL, timeout: float = 30.0) -> dict[tuple[str, str], FreeCandidate]:
    return build_free_candidates(fetch_models_dev_catalog(client=client, url=url, timeout=timeout))
