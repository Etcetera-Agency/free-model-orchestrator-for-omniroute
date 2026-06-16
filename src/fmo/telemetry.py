from dataclasses import dataclass


@dataclass(frozen=True)
class LatencyObservation:
    p95_ms: int
    granularity: str
    endpoint_exact: bool


@dataclass(frozen=True)
class DegradationResult:
    endpoint_status: str
    sibling_statuses: dict[str, str]


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
