from dataclasses import dataclass
from typing import Any

import httpx

from fmo.external_metadata import ExternalMetadataError


ARTIFICIAL_ANALYSIS_URL = "https://artificialanalysis.ai/api/v2/language/models"
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
    evaluations = row.get("evaluations") if isinstance(row.get("evaluations"), dict) else {}
    performance = row.get("performance") if isinstance(row.get("performance"), dict) else {}
    metrics = _extract_metrics(evaluations, performance)
    return AAModelMetrics(model_id=row["slug"], metrics=metrics, available=row.get("available"))


def _extract_metrics(evaluations: dict[str, Any], performance: dict[str, Any]) -> dict[str, float]:
    source = {
        "intelligence_index": evaluations.get("artificial_analysis_intelligence_index"),
        "coding_index": evaluations.get("artificial_analysis_coding_index"),
        "agentic_index": evaluations.get("artificial_analysis_agentic_index"),
        "median_output_tokens_per_second": performance.get("median_output_tokens_per_second"),
        "median_end_to_end_seconds": performance.get("median_end_to_end_seconds"),
    }
    return {key: value for key, value in source.items() if isinstance(value, int | float)}
