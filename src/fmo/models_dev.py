import time
from collections.abc import Callable
from typing import Any

import httpx

from fmo.candidates import FreeCandidate, build_free_candidates
from fmo.external_metadata import ExternalMetadataError

MODELS_DEV_API_URL = "https://models.dev/api.json"
MODELS_DEV_FETCH_ATTEMPTS = 3
TRANSIENT_MODELS_DEV_STATUSES = {502, 503, 504}


def fetch_models_dev_catalog(
    *,
    client=None,
    url: str = MODELS_DEV_API_URL,
    timeout: float = 30.0,
    attempts: int = MODELS_DEV_FETCH_ATTEMPTS,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    http_client = client or httpx
    bounded_attempts = max(1, attempts)
    # AICODE-NOTE: models.dev is fetched once per daily run; bounded retry
    # avoids losing a full run to one transient CDN/network failure.
    for attempt in range(bounded_attempts):
        try:
            response = http_client.get(url, timeout=timeout)
        except Exception as exc:
            if attempt + 1 < bounded_attempts:
                sleep(_transient_backoff_seconds(attempt))
                continue
            raise ExternalMetadataError("models_dev", "network_error") from exc
        if response.status_code == 429 and attempt + 1 < bounded_attempts:
            sleep(_retry_after_seconds(response.headers.get("Retry-After")))
            continue
        if response.status_code in TRANSIENT_MODELS_DEV_STATUSES and attempt + 1 < bounded_attempts:
            sleep(_transient_backoff_seconds(attempt))
            continue
        if response.status_code != 200:
            raise ExternalMetadataError("models_dev", "http_error", response.status_code)
        break
    try:
        payload = response.json()
    except Exception as exc:
        raise ExternalMetadataError("models_dev", "invalid_json") from exc
    return _normalize_catalog(payload)


def _transient_backoff_seconds(attempt: int) -> float:
    return min(1.0, 0.1 * (2**attempt))


def _retry_after_seconds(value: str | None) -> float:
    if not value:
        return 0.0
    try:
        return min(1.0, max(0.0, float(value)))
    except ValueError:
        return 0.0


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


def sync_models_dev_candidates(
    *,
    client=None,
    url: str = MODELS_DEV_API_URL,
    timeout: float = 30.0,
    attempts: int = MODELS_DEV_FETCH_ATTEMPTS,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[tuple[str, str], FreeCandidate]:
    return build_free_candidates(
        fetch_models_dev_catalog(client=client, url=url, timeout=timeout, attempts=attempts, sleep=sleep)
    )
