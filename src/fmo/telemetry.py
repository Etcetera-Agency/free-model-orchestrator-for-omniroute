from dataclasses import dataclass
from typing import Any

from fmo.omniroute import OmniRouteRequestError


@dataclass(frozen=True)
class LatencyObservation:
    p95_ms: int
    granularity: str
    endpoint_exact: bool


@dataclass(frozen=True)
class DegradationResult:
    endpoint_status: str
    sibling_statuses: dict[str, str]


@dataclass(frozen=True)
class TelemetryError(Exception):
    source: str
    reason: str
    status_code: int | None = None


@dataclass(frozen=True)
class TelemetryMetric:
    requests: int
    tokens: int | None
    avg_latency_ms: int | None
    p95_ms: int | None
    latency_granularity: str
    failure_count: int


@dataclass(frozen=True)
class TelemetrySnapshot:
    provider_metrics: dict[str, TelemetryMetric]
    model_metrics: dict[tuple[str, str], TelemetryMetric]
    errors: list[TelemetryError]


def normalize_latency(payload: dict, *, granularity: str) -> LatencyObservation:
    return LatencyObservation(
        p95_ms=payload["p95_ms"],
        granularity=granularity,
        endpoint_exact=granularity == "endpoint",
    )


def degrade_endpoint(health: dict, *, sibling_ids: list[str]) -> DegradationResult:
    degraded = health.get("consecutive_errors", 0) >= 3 or health.get("breaker") == "open"
    return DegradationResult(
        endpoint_status="degraded" if degraded else "active",
        sibling_statuses={sibling_id: "unchanged" for sibling_id in sibling_ids},
    )


def sync_live_telemetry(client: Any) -> TelemetrySnapshot:
    try:
        payload = _client_get(client, "/api/usage/analytics")
    except TelemetryError as exc:
        return TelemetrySnapshot(provider_metrics={}, model_metrics={}, errors=[exc])
    return TelemetrySnapshot(
        provider_metrics=_provider_metrics(payload),
        model_metrics=_model_metrics(payload),
        errors=[],
    )


def _provider_metrics(payload: dict[str, Any]) -> dict[str, TelemetryMetric]:
    metrics: dict[str, TelemetryMetric] = {}
    for item in payload.get("byProvider", []):
        if not isinstance(item, dict) or not item.get("provider"):
            continue
        metrics[str(item["provider"])] = _analytics_metric(item, granularity="provider")
    return metrics


def _model_metrics(payload: dict[str, Any]) -> dict[tuple[str, str], TelemetryMetric]:
    metrics: dict[tuple[str, str], TelemetryMetric] = {}
    for item in payload.get("byModel", []):
        if not isinstance(item, dict) or not item.get("provider") or not item.get("model"):
            continue
        metrics[(str(item["provider"]), str(item["model"]))] = _analytics_metric(item, granularity="provider")
    return metrics


def _analytics_metric(item: dict[str, Any], *, granularity: str) -> TelemetryMetric:
    requests = _int_value(item.get("requests"))
    success_rate = _float_value(item.get("successRatePct"))
    success_count = round(requests * success_rate / 100)
    return TelemetryMetric(
        requests=requests,
        tokens=_token_count(item),
        avg_latency_ms=_optional_int_value(item.get("avgLatencyMs")),
        p95_ms=None,
        latency_granularity=granularity,
        failure_count=max(0, requests - success_count),
    )


def _client_get(client: Any, path: str) -> dict[str, Any]:
    try:
        payload = client.get(path)
    except OmniRouteRequestError as exc:
        raise TelemetryError("omniroute_telemetry", "http_error", exc.status_code) from exc
    except Exception as exc:
        raise TelemetryError("omniroute_telemetry", "network_error") from exc
    if not isinstance(payload, dict):
        raise TelemetryError("omniroute_telemetry", "invalid_payload")
    return payload


def _int_value(value: Any) -> int:
    parsed = _optional_int_value(value)
    return parsed if parsed is not None else 0


def _optional_int_value(value: Any) -> int | None:
    if isinstance(value, int | float):
        return int(value)
    if isinstance(value, str) and value.strip():
        try:
            return int(float(value))
        except ValueError:
            return None
    return None


def _token_count(item: dict[str, Any]) -> int | None:
    for key in ("totalTokens", "tokens", "tokenCount"):
        parsed = _optional_int_value(item.get(key))
        if parsed is not None:
            return parsed
    prompt_tokens = _optional_int_value(item.get("promptTokens"))
    completion_tokens = _optional_int_value(item.get("completionTokens"))
    if prompt_tokens is None and completion_tokens is None:
        return None
    return (prompt_tokens or 0) + (completion_tokens or 0)


def _float_value(value: Any) -> float:
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return float(value)
        except ValueError:
            return 0.0
    return 0.0
