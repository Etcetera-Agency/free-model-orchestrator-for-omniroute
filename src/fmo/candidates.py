import re
from dataclasses import dataclass
from typing import Any


FREE_TOKEN_RE = re.compile(r"(^|[^a-z0-9])free([^a-z0-9]|$)")


@dataclass(frozen=True)
class FreeCandidate:
    provider_id: str
    model_id: str
    reasons: tuple[str, ...]
    display_name: str | None = None


def build_free_candidates(catalog: dict[str, Any]) -> dict[tuple[str, str], FreeCandidate]:
    candidates: dict[tuple[str, str], FreeCandidate] = {}
    for provider_id, provider in catalog.get("providers", {}).items():
        for model_id, model in provider.get("models", {}).items():
            reasons = _candidate_reasons(model_id, model)
            if reasons:
                candidates[(provider_id, model_id)] = FreeCandidate(
                    provider_id=provider_id,
                    model_id=model_id,
                    reasons=reasons,
                    display_name=model.get("name") or model.get("displayName"),
                )
    return candidates


def _candidate_reasons(model_id: str, model: dict[str, Any]) -> tuple[str, ...]:
    reasons = []
    cost = model.get("cost")
    if isinstance(cost, dict) and cost.get("input") == 0 and cost.get("output") == 0:
        reasons.append("zero_cost")
    if _has_free_token(model_id):
        reasons.append("free_in_model_id")
    display_name = model.get("name") or model.get("displayName") or ""
    if _has_free_token(display_name):
        reasons.append("free_in_display_name")
    if len(reasons) > 1:
        return ("multiple_signals",)
    return tuple(reasons)


def _has_free_token(value: str) -> bool:
    return bool(FREE_TOKEN_RE.search(value.lower()))
