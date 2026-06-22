import pytest

from fmo.quota_normalize import (
    DEFAULT_TOKENS_PER_REQUEST,
    CalibrationObservation,
    binding_capacity,
    recompute_derived_capacities,
    refine_global_tokens_per_request,
    to_requests_per_day,
)


@pytest.mark.spec("quota-manager::Request and token budgets normalize to daily requests")
def test_requests_per_day_passthrough():
    assert to_requests_per_day("requests", "day", 1000) == 1000


@pytest.mark.spec("quota-manager::Request and token budgets normalize to daily requests")
def test_requests_per_month_normalized_to_day():
    assert to_requests_per_day("requests", "month", 300) == 10


@pytest.mark.spec("quota-manager::Request and token budgets normalize to daily requests")
def test_tokens_per_day_converted_via_factor():
    # 2_000_000 tokens/day / 2000 tokens per request = 1000 req/day
    assert to_requests_per_day("tokens", "day", 2_000_000) == 1000


@pytest.mark.spec("quota-manager::Request and token budgets normalize to daily requests")
def test_tokens_per_month_normalized_and_converted():
    # 60M tokens/month -> 2M/day -> /2000 = 1000 req/day
    assert to_requests_per_day("tokens", "month", 60_000_000) == 1000


def test_custom_tokens_per_request_factor():
    assert to_requests_per_day("tokens", "day", 1000, tokens_per_request=100) == 10


@pytest.mark.parametrize("window", ["minute", "hour"])
@pytest.mark.spec("quota-manager::Reactive rate gates excluded from budget capacity")
def test_sub_day_windows_are_reactive_not_budget(window):
    assert to_requests_per_day("requests", window, 15) is None
    assert to_requests_per_day("tokens", window, 250_000) is None


def test_default_factor_is_2000():
    assert DEFAULT_TOKENS_PER_REQUEST == 2000


def test_invalid_metric_rejected():
    with pytest.raises(ValueError):
        to_requests_per_day("credits", "day", 100)


def test_non_positive_factor_rejected():
    with pytest.raises(ValueError):
        to_requests_per_day("tokens", "day", 100, tokens_per_request=0)


@pytest.mark.spec("quota-manager::Binding capacity uses tightest budget axis")
def test_binding_capacity_takes_tightest_axis():
    # RPD 1000 vs token budget 2M/day (=1000 req) vs token month 30M (=500 req)
    axes = [
        ("requests", "day", 1000),
        ("tokens", "day", 2_000_000),
        ("tokens", "month", 30_000_000),
    ]
    assert binding_capacity(axes) == 500


@pytest.mark.spec("quota-manager::Reactive rate gates excluded from budget capacity")
def test_binding_capacity_ignores_rate_gates():
    axes = [("requests", "minute", 15), ("requests", "day", 800)]
    assert binding_capacity(axes) == 800


@pytest.mark.spec("quota-manager::Reactive rate gates excluded from budget capacity")
def test_binding_capacity_none_when_no_budget_axis():
    assert binding_capacity([("requests", "minute", 15)]) is None
    assert binding_capacity([]) is None


def test_refine_factor_from_observations():
    # 1_500_000 tokens over 1000 requests -> 1500 tokens/request
    observations = [
        CalibrationObservation("a", 900_000, 600),
        CalibrationObservation("b", 600_000, 400),
    ]
    assert refine_global_tokens_per_request(observations, current=2000) == 1500


@pytest.mark.spec("quota-manager::Too little signal keeps the current factor")
def test_refine_keeps_current_when_too_few_requests():
    observations = [CalibrationObservation("a", 50_000, 10)]
    assert refine_global_tokens_per_request(observations, current=2000) == 2000


def test_refine_keeps_current_on_empty():
    assert refine_global_tokens_per_request([], current=2000) == 2000


@pytest.mark.spec("quota-manager::A noisy week is clamped")
def test_refine_clamps_downward_swing():
    # raw would be ~100, but clamp limits to 50% drop from 2000 -> 1000
    observations = [CalibrationObservation("a", 100_000, 1000)]
    assert refine_global_tokens_per_request(observations, current=2000) == 1000


def test_refine_clamps_upward_swing():
    # raw would be huge, clamp to +50% -> 3000
    observations = [CalibrationObservation("a", 10_000_000, 1000)]
    assert refine_global_tokens_per_request(observations, current=2000) == 3000


def test_recompute_only_touches_derived_sources():
    endpoints = [
        ("ep-search", "summary", [("tokens", "day", 2_000_000)]),
        ("ep-calc", "calibrated", [("requests", "day", 800)]),
        ("ep-live", "live", [("tokens", "day", 2_000_000)]),
    ]
    result = recompute_derived_capacities(endpoints, tokens_per_request=1000)
    assert result == {"ep-search": 2000, "ep-calc": 800}
    assert "ep-live" not in result
