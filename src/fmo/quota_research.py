import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from fmo.omniroute import OmniRouteRequestError


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


@dataclass(frozen=True)
class QuotaResearchError(Exception):
    source: str
    reason: str
    status_code: int | None = None


@dataclass(frozen=True)
class QuotaResearchResult:
    snapshot: SearchSnapshot | None
    rule: ActiveQuotaRule | None
    error: QuotaResearchError | None = None


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


def research_quota_rule(
    client: Any,
    *,
    provider: str,
    model_id: str,
    today: datetime,
    summary_confidence_cap: float,
    previous_limit: float | None = None,
) -> QuotaResearchResult:
    query = build_quota_query(provider, model_id, today=today)
    try:
        snapshot = run_quota_search(client, provider=provider, model_id=model_id, query=query)
        claim = extract_summary_claim(snapshot)
        rule = activate_summary_rule(
            claim,
            summary_confidence_cap=summary_confidence_cap,
            previous_limit=previous_limit,
        )
    except QuotaResearchError as exc:
        return QuotaResearchResult(snapshot=None, rule=None, error=exc)
    except OmniRouteRequestError as exc:
        error = QuotaResearchError("quota_research", "http_error", exc.status_code)
        return QuotaResearchResult(snapshot=None, rule=None, error=error)
    except Exception:
        error = QuotaResearchError("quota_research", "extraction_error")
        return QuotaResearchResult(snapshot=None, rule=None, error=error)
    return QuotaResearchResult(snapshot=snapshot, rule=rule)


def extract_summary_claim(snapshot: SearchSnapshot) -> QuotaClaim:
    amount = _extract_amount(snapshot.answer_text)
    window = _extract_window(snapshot.answer_text)
    hard_stop = "hard stop" in snapshot.answer_text.lower()
    claim = QuotaClaim(
        metric="requests",
        amount=amount,
        window=window,
        evidence=list(snapshot.evidence_urls) or ["summary"],
        hard_stop=hard_stop,
    )
    return validate_claim(claim)


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


def _extract_amount(text: str) -> float:
    match = re.search(r"\b(\d+(?:\.\d+)?)\s+requests?\b", text, re.IGNORECASE)
    if not match:
        raise QuotaResearchError("quota_research", "missing_amount")
    return float(match.group(1))


def _extract_window(text: str) -> str:
    lowered = text.lower()
    for window in ("minute", "hour", "day", "month"):
        if f"per {window}" in lowered or f"/{window}" in lowered:
            return window
    raise QuotaResearchError("quota_research", "missing_window")


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
