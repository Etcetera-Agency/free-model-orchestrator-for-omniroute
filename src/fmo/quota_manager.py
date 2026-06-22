from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from fmo.omniroute import OmniRouteRequestError
from fmo.quota_normalize import DEFAULT_TOKENS_PER_REQUEST, binding_capacity, to_requests_per_day


@dataclass(frozen=True)
class QuotaFetchError(Exception):
    source: str
    reason: str
    status_code: int | None = None


@dataclass(frozen=True)
class LiveQuota:
    provider: str
    connection_id: str
    limit: float | None
    remaining: float | None
    reset_at: datetime | None


@dataclass(frozen=True)
class LiveQuotaSnapshot:
    observed_at: datetime
    quotas: dict[str, LiveQuota]


def effective_remaining(
    *,
    limit: float | None,
    provider_remaining: float | None,
    local_used: float | None,
    pending_reserved: float,
    safety_buffer: float,
) -> float | None:
    reliable_values = []
    if provider_remaining is not None:
        reliable_values.append(provider_remaining)
    if limit is not None and local_used is not None:
        reliable_values.append(limit - local_used)
    if not reliable_values:
        return None
    return min(reliable_values) - pending_reserved - safety_buffer


def require_hard_stop(hard_stop_capable: bool) -> None:
    if not hard_stop_capable:
        raise ValueError("hard stop required")


def validate_historical_reserve(record: dict) -> None:
    if record.get("source") == "historical" and not record.get("reserve_applied"):
        raise ValueError("historical reserve missing")


def reset_and_reclassify(fetch_live_quota: Callable[[], dict], reclassify: Callable[[dict], object]) -> object:
    live_quota = fetch_live_quota()
    return reclassify(live_quota)


def fetch_live_quota_snapshot(
    client: Any,
    *,
    now: datetime | None = None,
    max_age: timedelta = timedelta(minutes=15),
    tokens_per_request: int = DEFAULT_TOKENS_PER_REQUEST,
) -> LiveQuotaSnapshot:
    now = now or datetime.now(timezone.utc)
    payload = _client_get(client, "/api/usage/quota")
    generated_at = _parse_timestamp(payload.get("meta", {}).get("generatedAt"))
    if generated_at is None:
        raise QuotaFetchError("omniroute_quota", "missing_generated_at")
    if generated_at < now - max_age:
        raise QuotaFetchError("omniroute_quota", "stale_data")

    providers = payload.get("providers")
    if not isinstance(providers, list):
        raise QuotaFetchError("omniroute_quota", "invalid_payload")

    quotas: dict[str, LiveQuota] = {}
    for item in providers:
        if not isinstance(item, dict):
            raise QuotaFetchError("omniroute_quota", "invalid_payload")
        quota = _normalize_quota(item, tokens_per_request=tokens_per_request)
        quotas[f"{quota.provider}:{quota.connection_id}"] = quota
    return LiveQuotaSnapshot(observed_at=generated_at, quotas=quotas)


def endpoint_binding_capacity(
    *,
    research_rule: Any | None = None,
    calibration_rule: Any | None = None,
    live_quota: LiveQuota | None = None,
    tokens_per_request: int = DEFAULT_TOKENS_PER_REQUEST,
) -> float | None:
    axes = endpoint_quota_axes(
        research_rule=research_rule,
        calibration_rule=calibration_rule,
        live_quota=live_quota,
    )
    return binding_capacity(axes, tokens_per_request=tokens_per_request)


def endpoint_quota_axes(
    *,
    research_rule: Any | None = None,
    calibration_rule: Any | None = None,
    live_quota: LiveQuota | None = None,
) -> list[tuple[str, str, float]]:
    axes: list[tuple[str, str, float]] = []
    axes.extend(_rule_axes(research_rule))
    axes.extend(_rule_axes(calibration_rule))
    if live_quota and live_quota.limit is not None:
        axes.append(("requests", "day", live_quota.limit))
    return axes


def fail_closed_quota_evidence(error: QuotaFetchError) -> dict[str, Any]:
    return {
        "quota_rule": True,
        "limit": None,
        "remaining": None,
        "reset_at": None,
        "hard_stop": False,
        "quota_error": error.reason,
    }


def _client_get(client: Any, path: str) -> dict[str, Any]:
    try:
        payload = client.get(path)
    except OmniRouteRequestError as exc:
        raise QuotaFetchError("omniroute_quota", "http_error", exc.status_code) from exc
    except Exception as exc:
        raise QuotaFetchError("omniroute_quota", "network_error") from exc
    if not isinstance(payload, dict):
        raise QuotaFetchError("omniroute_quota", "invalid_payload")
    return payload


def _normalize_quota(item: dict[str, Any], *, tokens_per_request: int) -> LiveQuota:
    provider = str(item.get("provider") or "unknown")
    connection_id = str(item.get("connectionId") or "unknown")
    limit_tokens = _number_or_none(item.get("monthlyTokens"))
    window = "month" if limit_tokens is not None else str(item.get("quotaWindow") or "day")
    if limit_tokens is None:
        limit_tokens = _number_or_none(item.get("quotaTotal"))
    used_tokens = _number_or_none(item.get("quotaUsed"))
    limit = _tokens_to_requests_per_day(limit_tokens, window=window, tokens_per_request=tokens_per_request)
    used = _tokens_to_requests_per_day(used_tokens, window=window, tokens_per_request=tokens_per_request)
    remaining = limit - used if limit is not None and used is not None else None
    return LiveQuota(
        provider=provider,
        connection_id=connection_id,
        limit=limit,
        remaining=remaining,
        reset_at=_parse_timestamp(item.get("resetAt")),
    )


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _number_or_none(value: Any) -> float | None:
    return float(value) if isinstance(value, int | float) else None


def _tokens_to_requests_per_day(value: float | None, *, window: str, tokens_per_request: int) -> float | None:
    if value is None:
        return None
    try:
        return to_requests_per_day("tokens", window, value, tokens_per_request=tokens_per_request)
    except ValueError as exc:
        raise QuotaFetchError("omniroute_quota", "invalid_payload") from exc


def _rule_axes(rule: Any | None) -> list[tuple[str, str, float]]:
    if rule is None:
        return []
    claims = getattr(rule, "axes", None) or (getattr(rule, "claim"),)
    return [(claim.metric, claim.window, claim.amount) for claim in claims]
