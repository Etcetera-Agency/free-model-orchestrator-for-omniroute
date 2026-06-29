"""Unit coverage for the request-window reset horizon in apply safety.

A minute/hour request-window rule may bypass locked_out/reset only when the
reset is imminent (within the horizon). A far-future reset must still hard-stop.
"""

from datetime import UTC, datetime, timedelta

import pytest

from fmo.composition_stages.apply import _endpoint_quota_row_is_safe

_NOW = datetime(2026, 6, 24, 12, 0, tzinfo=UTC)


def _request_window_row(*, reset_at, locked_out):
    return {
        "status": "confirmed",
        "hard_stop_capable": True,
        "effective_remaining": {"requests": 100},
        "reset_at": reset_at,
        "classified_at": _NOW,
        "valid_until": None,
        "quota_rule_limits": {"window": "minute", "requests": 100},
        "evidence": {
            "remaining_source": "live_observed",
            "quota_rule": True,
            "daily_budget_source": "research",
            "hard_stop": True,
            "locked_out": locked_out,
            "safety_buffer": 0,
            "percent_remaining": 0,
        },
    }


def _is_safe(row):
    return _endpoint_quota_row_is_safe(
        row,
        now=_NOW,
        oldest_allowed=_NOW - timedelta(hours=24),
        minimum_safety_buffer=4,
        minimum_percent_remaining=0.0,
    )


@pytest.mark.spec("combo-applier::Request-window hard-stop quota can satisfy apply safety")
def test_imminent_reset_bypasses_locked_out():
    row = _request_window_row(reset_at=_NOW + timedelta(minutes=5), locked_out=True)
    assert _is_safe(row) is True


@pytest.mark.spec("combo-applier::Far-future reset hard-stops a request-window endpoint")
def test_far_future_reset_with_lockout_hard_stops():
    row = _request_window_row(reset_at=_NOW + timedelta(hours=6), locked_out=True)
    assert _is_safe(row) is False


@pytest.mark.spec("combo-applier::Far-future reset hard-stops a request-window endpoint")
def test_far_future_reset_blocks_even_without_lockout():
    row = _request_window_row(reset_at=_NOW + timedelta(hours=6), locked_out=False)
    assert _is_safe(row) is False
