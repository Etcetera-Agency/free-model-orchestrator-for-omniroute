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
    canonical_slug: str | None = None


FORBIDDEN_VARIANTS = ("preview", "thinking", "instruct", "base", "mini")


def match_model(
    provider_model_id: str,
    *,
    canonical_slugs: set[str],
    provider_catalog_ids: set[str],
    preferred_canonical_slugs: set[str] | None = None,
) -> MatchResult:
    normalized_candidates = _normalized_candidates(provider_model_id)
    primary_normalized = normalized_candidates[0]
    preferred = preferred_canonical_slugs or set()
    for candidate in normalized_candidates:
        if candidate in preferred:
            return _result(MatchMethod.EXACT_SLUG, 0.95, canonical_slug=candidate)
    for candidate in normalized_candidates:
        if candidate in canonical_slugs:
            return _result(MatchMethod.EXACT_SLUG, 0.95, canonical_slug=candidate)
    if any(token in primary_normalized.split("-") for token in FORBIDDEN_VARIANTS):
        return _result(MatchMethod.REVIEW_REQUIRED, 0.85)
    if provider_model_id in provider_catalog_ids:
        return _result(MatchMethod.EXACT_PROVIDER_CATALOG, 0.98, canonical_slug=primary_normalized)
    return _result(MatchMethod.UNMATCHED, 0.0)


def effective_context(*, canonical_context: int | None, provider_context: int | None) -> int | None:
    values = [value for value in (canonical_context, provider_context) if value is not None]
    if not values:
        return None
    return min(values)


def _result(method: MatchMethod, confidence: float, *, canonical_slug: str | None = None) -> MatchResult:
    return MatchResult(
        method=method,
        confidence=confidence,
        auto_use=confidence >= 0.90,
        review_required=confidence < 0.90,
        canonical_slug=canonical_slug,
    )


def _normalize(model_id: str) -> str:
    return model_id.lower().split("/")[-1].replace("_", "-")


def _normalized_candidates(model_id: str) -> list[str]:
    normalized = _normalize(model_id)
    candidates = [normalized]
    dotted = normalized.replace(".", "-")
    if dotted not in candidates:
        candidates.append(dotted)
    for candidate in tuple(candidates):
        if candidate.endswith("-it"):
            stripped = candidate.removesuffix("-it")
            if stripped not in candidates:
                candidates.append(stripped)
    return candidates
