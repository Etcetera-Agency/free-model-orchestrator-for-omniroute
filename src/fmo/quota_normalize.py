"""Normalize heterogeneous quota limits to a single comparable unit.

Quota data is heterogeneous: some endpoints expose only token budgets, others
only request limits. Forecast and allocation need one comparable magnitude, and
demand is natively in requests (calls), so everything is reduced to
**request-equivalents per day**.

Token budgets are converted with a flat ``tokens_per_request`` factor (default
2000, configurable). Request rate windows (minute/hour) are extrapolated to a
request-equivalent daily ceiling and then discounted, because sustaining the
peak rate 24/7 is unrealistic; sub-day token windows are not used for planning.
"""

from dataclasses import dataclass
from typing import Any

DEFAULT_TOKENS_PER_REQUEST = 2000

_REQUEST_WINDOW_MULTIPLIERS = {"minute": 1440, "hour": 24, "day": 1, "month": 1 / 30}
# Sub-day request windows are extrapolated up from a peak rate, so discount the
# daily ceiling to avoid overstating planning capacity for RPM-only providers.
_EXTRAPOLATED_REQUEST_WINDOWS = {"minute", "hour"}
_RATE_EXTRAPOLATION_DISCOUNT = 0.8
_TOKEN_WINDOW_DAYS = {"day": 1, "month": 30}
_VALID_METRICS = {"requests", "tokens"}
_QUOTA_METRICS = ("requests", "tokens")

# Quota whose numbers we derived ourselves (search summary or self-calculated
# calibration) rather than read from an authoritative live source. Only these are
# recomputed when the global tokens-per-request factor is refined.
DERIVED_SOURCES = {"summary", "calibrated"}


def quota_metric(limits: Any) -> tuple[str, float]:
    """Return the quota metric and amount stored in a quota limits payload."""
    mapping = limits if isinstance(limits, dict) else None
    for metric in _QUOTA_METRICS:
        if mapping is not None:
            if metric in mapping:
                return metric, float(mapping[metric] or 0)
        else:
            try:
                return metric, float(limits[metric] or 0)
            except (KeyError, TypeError):
                continue
    return "requests", 0.0


def quota_limit(limits: Any) -> float:
    return quota_metric(limits)[1]


def remaining_amount(effective_remaining: Any) -> float:
    """Remaining quota regardless of which metric key is stored."""
    if isinstance(effective_remaining, dict):
        for metric in _QUOTA_METRICS:
            if metric in effective_remaining:
                return float(effective_remaining[metric] or 0)
        return 0.0
    for metric in _QUOTA_METRICS:
        try:
            return float(effective_remaining[metric] or 0)
        except (KeyError, TypeError):
            continue
    return 0.0


def to_requests_per_day(
    metric: str,
    window: str,
    amount: float,
    *,
    tokens_per_request: int = DEFAULT_TOKENS_PER_REQUEST,
) -> float | None:
    """Convert one quota axis to request-equivalents per day.

    Returns ``None`` for sub-day token windows.
    """
    if metric not in _VALID_METRICS:
        raise ValueError(f"invalid quota metric: {metric!r}")
    if tokens_per_request <= 0:
        raise ValueError("tokens_per_request must be positive")
    if metric == "requests":
        multiplier = _REQUEST_WINDOW_MULTIPLIERS.get(window)
        if multiplier is None:
            return None
        daily = amount * multiplier
        if window in _EXTRAPOLATED_REQUEST_WINDOWS:
            daily *= _RATE_EXTRAPOLATION_DISCOUNT
        return daily
    window_days = _TOKEN_WINDOW_DAYS.get(window)
    if window_days is None:
        return None
    per_day = amount / window_days
    if metric == "tokens":
        return per_day / tokens_per_request
    return per_day


def binding_capacity(
    axes: list[tuple[str, str, float]],
    *,
    tokens_per_request: int = DEFAULT_TOKENS_PER_REQUEST,
) -> float | None:
    """Capacity in request-equivalents per day, bound by the tightest axis.

    ``axes`` is a list of ``(metric, window, amount)``. Returns ``None`` when no
    usable capacity axis is known.
    """
    values = [
        value
        for metric, window, amount in axes
        if (value := to_requests_per_day(metric, window, amount, tokens_per_request=tokens_per_request)) is not None
    ]
    return min(values) if values else None


@dataclass(frozen=True)
class CalibrationObservation:
    """Observed real usage for one endpoint, gathered by the calibration module."""

    provider: str
    observed_tokens: float
    observed_requests: float


def refine_global_tokens_per_request(
    observations: list[CalibrationObservation],
    *,
    current: int,
    min_total_requests: int = 100,
    max_change_ratio: float = 0.5,
) -> int:
    """Refine the global tokens-per-request factor from real observations.

    Aggregates observed tokens and requests across all calibration samples.
    Returns ``current`` unchanged when there is too little signal
    (``min_total_requests``). The result is clamped to within
    ``max_change_ratio`` of ``current`` so one noisy week cannot swing the
    factor that every derived provider depends on.
    """
    total_tokens = sum(observation.observed_tokens for observation in observations)
    total_requests = sum(observation.observed_requests for observation in observations)
    if total_requests < min_total_requests:
        return current
    refined = round(total_tokens / total_requests)
    if refined <= 0:
        return current
    lower = round(current * (1 - max_change_ratio))
    upper = round(current * (1 + max_change_ratio))
    return max(lower, min(upper, refined))


def recompute_derived_capacities(
    endpoints: list[tuple[str, str, list[tuple[str, str, float]]]],
    *,
    tokens_per_request: int,
) -> dict[str, float | None]:
    """Recompute capacity (req/day) for self-derived endpoints under a new factor.

    ``endpoints`` is a list of ``(endpoint_id, source, axes)``. Only endpoints
    whose ``source`` is in :data:`DERIVED_SOURCES` are recomputed; authoritative
    live-quota endpoints are left untouched.
    """
    return {
        endpoint_id: binding_capacity(axes, tokens_per_request=tokens_per_request)
        for endpoint_id, source, axes in endpoints
        if source in DERIVED_SOURCES
    }
