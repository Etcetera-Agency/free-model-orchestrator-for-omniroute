from dataclasses import dataclass
from enum import Enum


class MatchMethod(str, Enum):
    EXACT_PROVIDER_CATALOG = "exact_provider_catalog"
    EXACT_SLUG = "exact_slug"
    REVIEW_REQUIRED = "review_required"
    UNMATCHED = "unmatched"


@dataclass(frozen=True)
class MatchResult:
    method: MatchMethod
    confidence: float
    auto_use: bool
    review_required: bool


FORBIDDEN_VARIANTS = ("preview", "thinking", "instruct", "base", "mini")


def match_model(
    provider_model_id: str,
    *,
    canonical_slugs: set[str],
    provider_catalog_ids: set[str],
) -> MatchResult:
    normalized = _normalize(provider_model_id)
    if provider_model_id in provider_catalog_ids:
        return _result(MatchMethod.EXACT_PROVIDER_CATALOG, 0.98)
    if normalized in canonical_slugs:
        return _result(MatchMethod.EXACT_SLUG, 0.95)
    if any(token in normalized.split("-") for token in FORBIDDEN_VARIANTS):
        return _result(MatchMethod.REVIEW_REQUIRED, 0.85)
    return _result(MatchMethod.UNMATCHED, 0.0)


def effective_context(*, canonical_context: int | None, provider_context: int | None) -> int | None:
    values = [value for value in (canonical_context, provider_context) if value is not None]
    if not values:
        return None
    return min(values)


def _result(method: MatchMethod, confidence: float) -> MatchResult:
    return MatchResult(
        method=method,
        confidence=confidence,
        auto_use=confidence >= 0.90,
        review_required=confidence < 0.90,
    )


def _normalize(model_id: str) -> str:
    return model_id.lower().split("/")[-1].replace("_", "-")
