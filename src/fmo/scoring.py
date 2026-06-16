from dataclasses import dataclass


ALLOWED_ACCESS = {"free_unlimited", "free_quota_available", "free_promotional_available"}


@dataclass(frozen=True)
class EligibilityDecision:
    eligible: bool
    reason: str | None = None


@dataclass(frozen=True)
class AASubscore:
    value: float | None
    uncertainty_penalty: float
    unknown: bool = False


@dataclass(frozen=True)
class ScoreResult:
    total: float
    components: dict[str, float]


def eligible_for_scoring(endpoint: dict, *, required_capabilities: set[str]) -> EligibilityDecision:
    if endpoint.get("access") not in ALLOWED_ACCESS:
        return EligibilityDecision(False, "access")
    if not endpoint.get("basic_probe"):
        return EligibilityDecision(False, "probe")
    if endpoint.get("quota", 0) <= 0:
        return EligibilityDecision(False, "quota")
    if not endpoint.get("matched"):
        return EligibilityDecision(False, "match")
    if endpoint.get("breaker") != "closed":
        return EligibilityDecision(False, "breaker")
    if not required_capabilities.issubset(set(endpoint.get("capabilities", set()))):
        return EligibilityDecision(False, "capabilities")
    return EligibilityDecision(True)


def aa_subscore(metrics: dict[str, float], *, weights: dict[str, float], percentiles: dict[str, tuple[float, float]]) -> AASubscore:
    quality_keys = {"intelligence_index", "coding_index", "agentic_index"}
    present = [key for key in weights if key in metrics and key in percentiles]
    if not quality_keys.intersection(present):
        return AASubscore(value=None, uncertainty_penalty=0, unknown=True)
    total_weight = sum(weights[key] for key in present)
    value = sum(_normalize(metrics[key], *percentiles[key]) * (weights[key] / total_weight) for key in present)
    missing_count = len([key for key in weights if key not in present])
    return AASubscore(value=value, uncertainty_penalty=missing_count * 0.05)


def latency_score_source(*, endpoint_p95: int | None, provider_p95: int | None, aa_latency: float | None) -> tuple[str, float | None]:
    if endpoint_p95 is not None:
        return ("endpoint", endpoint_p95)
    if provider_p95 is not None:
        return ("provider", provider_p95)
    if aa_latency is not None:
        return ("aa", aa_latency)
    return ("unknown", None)


def score_endpoint(components: dict[str, float]) -> ScoreResult:
    used = {
        key: components.get(key, 0)
        for key in ("benchmark_fit", "capability_fit", "health", "latency", "quota_headroom", "stability")
    }
    total = sum(used.values()) - components.get("uncertainty", 0)
    return ScoreResult(total=total, components=used)


def should_recompute_score(previous_hash: str | None, current_hash: str) -> bool:
    return previous_hash != current_hash


def _normalize(value: float, p5: float, p95: float) -> float:
    if p95 <= p5:
        return 0.0
    clipped = min(max(value, p5), p95)
    return (clipped - p5) / (p95 - p5)
