from typing import Callable


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
