from dataclasses import dataclass
from enum import Enum


class MatchMethod(str, Enum):
    EXACT_SLUG = "exact_slug"
    NEW_CANONICAL = "new_canonical"
    REVIEW_REQUIRED = "review_required"


@dataclass(frozen=True)
class MatchResult:
    method: MatchMethod
    confidence: float
    auto_use: bool
    review_required: bool
    canonical_slug: str | None = None


def match_model(
    provider_model_id: str,
    *,
    canonical_slugs: set[str],
    preferred_canonical_slugs: set[str] | None = None,
) -> MatchResult:
    # AICODE-NOTE: Artificial Analysis scores variants (-thinking, -reasoning,
    # -instruct, -base, -mini, ...) as distinct models, so we bind to the full
    # variant slug, most specific candidate first. Distinct variants therefore
    # get distinct canonical rows and are never auto-merged (model-matcher spec).
    candidates = canonical_slug_candidates(provider_model_id)
    primary = candidates[0]
    preferred = preferred_canonical_slugs or set()
    for candidate in candidates:
        if candidate in preferred:
            return _result(MatchMethod.EXACT_SLUG, 0.97, canonical_slug=candidate)
    for candidate in candidates:
        if candidate in canonical_slugs:
            return _result(MatchMethod.EXACT_SLUG, 0.95, canonical_slug=candidate)
    # No known canonical: register a variant-specific canonical from the full
    # slug instead of parking the model in review. Suffixes are preserved, so a
    # base and its instruct/thinking sibling resolve to different canonical rows.
    return _result(MatchMethod.NEW_CANONICAL, 0.90, canonical_slug=primary)


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


def canonical_slug_candidates(model_id: str) -> list[str]:
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
