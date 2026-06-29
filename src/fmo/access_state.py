from __future__ import annotations

from typing import Any


def remaining_amount(value: Any) -> float:
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, dict):
        for key in ("requests", "remaining", "amount"):
            amount = value.get(key)
            if isinstance(amount, int | float):
                return float(amount)
    return 0.0
