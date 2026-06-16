import hashlib
from dataclasses import dataclass
from datetime import datetime


VALID_METRICS = {"requests", "tokens"}
VALID_WINDOWS = {"minute", "hour", "day", "month"}


@dataclass(frozen=True)
class SearchSnapshot:
    query: str
    answer_text: str
    evidence_urls: tuple[str, ...]
    content_hash: str


@dataclass(frozen=True)
class QuotaClaim:
    metric: str
    amount: float
    window: str
    evidence: list[str]
    hard_stop: bool


@dataclass(frozen=True)
class ActiveQuotaRule:
    claim: QuotaClaim
    confidence: float
    activated_by: str
    capacity_class: str
    safe_mode: bool


def build_quota_query(provider: str, model_id: str, *, today: datetime) -> str:
    return f"{provider} free tier quota for {model_id} today {today:%Y-%m-%d}"


def run_quota_search(client, *, provider: str, model_id: str, query: str) -> SearchSnapshot:
    response = client.post(
        "/v1/search",
        {"query": query, "provider": "gemini-grounded-search", "search_type": "web", "max_results": 10, "time_range": "month"},
    )
    answer_text = response.get("answer", {}).get("text", "")
    urls = tuple(result["url"] for result in response.get("results", []) if result.get("url"))
    content_hash = hashlib.sha256((query + answer_text + "".join(urls)).encode("utf-8")).hexdigest()
    return SearchSnapshot(query=query, answer_text=answer_text, evidence_urls=urls, content_hash=content_hash)


def validate_claim(claim: QuotaClaim) -> QuotaClaim:
    if claim.metric not in VALID_METRICS:
        raise ValueError("invalid quota metric")
    if claim.amount <= 0:
        raise ValueError("quota amount must be positive")
    if claim.window not in VALID_WINDOWS:
        raise ValueError("invalid quota window")
    if not claim.evidence:
        raise ValueError("quota claim requires evidence")
    return claim


def activate_summary_rule(claim: QuotaClaim, *, summary_confidence_cap: float, previous_limit: float | None = None) -> ActiveQuotaRule:
    validate_claim(claim)
    safe_mode = previous_limit is not None and claim.amount < previous_limit
    return ActiveQuotaRule(
        claim=claim,
        confidence=summary_confidence_cap,
        activated_by="summary",
        capacity_class="opportunistic",
        safe_mode=safe_mode,
    )
