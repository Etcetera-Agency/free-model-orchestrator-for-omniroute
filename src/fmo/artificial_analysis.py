from dataclasses import dataclass
from typing import Any, cast

import httpx

from fmo.external_metadata import ExternalMetadataError

ARTIFICIAL_ANALYSIS_URL = "https://artificialanalysis.ai/api/v2/language/models"
ARTIFICIAL_ANALYSIS_FREE_URL = "https://artificialanalysis.ai/api/v2/language/models/free"
FREE_PAGE_SIZE = 200
MAX_FREE_PAGES = 50
SCORING_METRICS = (
    "intelligence_index",
    "coding_index",
    "agentic_index",
    "median_output_tokens_per_second",
    "median_end_to_end_seconds",
)


@dataclass(frozen=True)
class AAModelMetrics:
    model_id: str
    metrics: dict[str, float]
    available: bool | None = None


@dataclass(frozen=True)
class AASnapshot:
    index_version: str
    models: tuple[AAModelMetrics, ...]


def fetch_artificial_analysis_snapshot(
    *,
    api_key: str | None,
    client=None,
    url: str = ARTIFICIAL_ANALYSIS_URL,
    timeout: float = 30.0,
) -> AASnapshot:
    if not api_key:
        raise ExternalMetadataError("artificial_analysis", "aa_api_key_required")
    http_client = client or httpx
    try:
        response = http_client.get(url, headers={"x-api-key": api_key}, timeout=timeout)
    except Exception as exc:
        raise ExternalMetadataError("artificial_analysis", "network_error") from exc
    if response.status_code != 200:
        raise ExternalMetadataError("artificial_analysis", "http_error", response.status_code)
    try:
        payload = response.json()
    except Exception as exc:
        raise ExternalMetadataError("artificial_analysis", "invalid_json") from exc
    return _parse_snapshot(payload)


def fetch_artificial_analysis_free_snapshot(
    *,
    api_key: str | None,
    client=None,
    url: str = ARTIFICIAL_ANALYSIS_FREE_URL,
    page_size: int = FREE_PAGE_SIZE,
    timeout: float = 30.0,
) -> AASnapshot:
    """Aggregate every page of the free-tier endpoint into one snapshot.

    Pro-gated ``/api/v2/language/models`` is unavailable to this project, so
    production ingestion reads ``/api/v2/language/models/free`` and follows the
    response ``pagination`` (``has_more`` / ``total_pages``) until exhausted.
    """
    if not api_key:
        raise ExternalMetadataError("artificial_analysis", "aa_api_key_required")
    http_client = client or httpx
    index_version: str | None = None
    models: list[AAModelMetrics] = []
    page = 1
    while page <= MAX_FREE_PAGES:
        body = _get_free_page(http_client, url, api_key, page, page_size, timeout)
        snapshot = _parse_snapshot(body)
        index_version = index_version or snapshot.index_version
        models.extend(snapshot.models)
        if not _has_more_pages(body, page):
            break
        page += 1
    if index_version is None:
        raise ExternalMetadataError("artificial_analysis", "invalid_payload")
    return AASnapshot(index_version=index_version, models=tuple(models))


def _get_free_page(
    http_client: Any,
    url: str,
    api_key: str,
    page: int,
    page_size: int,
    timeout: float,
) -> Any:
    try:
        response = http_client.get(
            url,
            headers={"x-api-key": api_key},
            params={"page": page, "page_size": page_size},
            timeout=timeout,
        )
    except Exception as exc:
        raise ExternalMetadataError("artificial_analysis", "network_error") from exc
    if response.status_code != 200:
        raise ExternalMetadataError("artificial_analysis", "http_error", response.status_code)
    try:
        return response.json()
    except Exception as exc:
        raise ExternalMetadataError("artificial_analysis", "invalid_json") from exc


def _has_more_pages(body: Any, page: int) -> bool:
    pagination = body.get("pagination") if isinstance(body, dict) else None
    if not isinstance(pagination, dict):
        return False
    if isinstance(pagination.get("has_more"), bool):
        return pagination["has_more"]
    total_pages = pagination.get("total_pages")
    if isinstance(total_pages, int):
        return page < total_pages
    return False


def _parse_snapshot(payload: Any) -> AASnapshot:
    if not isinstance(payload, dict):
        raise ExternalMetadataError("artificial_analysis", "invalid_payload")
    index_version = payload.get("intelligence_index_version")
    rows = payload.get("data")
    if not isinstance(index_version, str | int | float) or not str(index_version) or not isinstance(rows, list):
        raise ExternalMetadataError("artificial_analysis", "invalid_payload")
    return AASnapshot(index_version=str(index_version), models=tuple(_parse_model(row) for row in rows))


def _parse_model(row: Any) -> AAModelMetrics:
    if not isinstance(row, dict) or not isinstance(row.get("slug"), str):
        raise ExternalMetadataError("artificial_analysis", "invalid_payload")
    evaluations = cast(dict[str, Any], row.get("evaluations") if isinstance(row.get("evaluations"), dict) else {})
    performance = cast(dict[str, Any], row.get("performance") if isinstance(row.get("performance"), dict) else {})
    metrics = _extract_metrics(evaluations, performance)
    return AAModelMetrics(model_id=row["slug"], metrics=metrics, available=row.get("available"))


def _extract_metrics(evaluations: dict[str, Any], performance: dict[str, Any]) -> dict[str, float]:
    source = {
        "intelligence_index": evaluations.get("artificial_analysis_intelligence_index"),
        "coding_index": evaluations.get("artificial_analysis_coding_index"),
        "agentic_index": evaluations.get("artificial_analysis_agentic_index"),
        "median_output_tokens_per_second": performance.get("median_output_tokens_per_second"),
        "median_end_to_end_seconds": performance.get("median_end_to_end_seconds")
        if performance.get("median_end_to_end_seconds") is not None
        else performance.get("median_end_to_end_response_time_seconds"),
    }
    return {key: value for key, value in source.items() if isinstance(value, int | float)}
