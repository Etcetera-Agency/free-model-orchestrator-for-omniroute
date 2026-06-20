from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeCliResult:
    exit_code: int
    changed: bool
    combo_test_called: bool = False
    error_reason: str | None = None
    output: str | None = None
