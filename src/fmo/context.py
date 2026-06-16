from dataclasses import dataclass


@dataclass(frozen=True)
class ContextDecision:
    eligible: bool
    bonus: int = 0


def effective_context_window(values: list[int | None]) -> int | None:
    known = [value for value in values if value is not None]
    if not known:
        return None
    return min(known)


def context_eligible(
    *,
    effective_context: int | None,
    minimum_context: int,
    manual_override: bool = False,
) -> ContextDecision:
    if effective_context is None:
        return ContextDecision(eligible=manual_override)
    return ContextDecision(eligible=effective_context >= minimum_context, bonus=0)
