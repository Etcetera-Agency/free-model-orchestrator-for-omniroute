import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from fmo.llm_runtime import LlmSiteConfig, complete_with_adapter
from fmo.omniroute import OmniRouteRequestError

VALID_METRICS = {"requests", "tokens"}
VALID_WINDOWS = {"minute", "hour", "day", "month"}
# AICODE-NOTE: no-auth aliases are shared quota/model pools, not independent
# capacity; missing sibling evidence must stay inactive.
NOAUTH_QUOTA_ALIASES = {"opencode": "opencode-zen"}
NOAUTH_CALIBRATION_ACTION = "place_first_in_combo_and_observe_omniroute_token_usage"
QUOTA_INSPECTOR_PROMPT = Path(__file__).resolve().parents[2] / "reference" / "prompts" / "quota-research.md"


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
    axes: tuple[QuotaClaim, ...] = ()


@dataclass(frozen=True)
class NoAuthQuotaResolution:
    provider: str
    model_id: str
    status: str
    usable: bool
    rule: ActiveQuotaRule | None = None
    quota_source_provider: str | None = None
    model_source_provider: str | None = None
    shared_with: str | None = None
    model_ids: tuple[str, ...] = ()
    independence_status: str = "unknown"
    counted_as_independent: bool = False
    action: str | None = None


@dataclass(frozen=True)
class NoAuthCalibrationEvidence:
    observed_tokens: float | None = None
    inferred_limit: float | None = None
    reset_window: str | None = None
    hard_stop: bool | None = None
    evidence: tuple[str, ...] = ()


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


class QuotaClaimResponse(BaseModel):
    metric: str
    amount: float
    window: str
    evidence: list[str] = Field(default_factory=list)
    hard_stop: bool = False


def build_quota_query(provider: str, model_id: str, *, today: datetime) -> str:
    return (
        f"What is the free-tier usage quota for {provider} model {model_id}, current as of {today:%Y-%m-%d}? "
        "Give the cumulative daily and monthly limits, both in requests and in tokens: requests per day, "
        "requests per month, tokens per day, tokens per month. Ignore per-minute/per-second rate limits "
        "(RPM/TPM). State whether hitting the quota is a hard stop (requests blocked) or a soft throttle. "
        "Search broadly: official documentation plus community sources such as developer forums, Reddit, "
        "GitHub issues, Discord, and Stack Overflow. Prefer the official documentation URL as evidence, "
        "but include community source URLs when they report current real-world limits."
    )


def run_quota_search(client, *, provider: str, model_id: str, query: str) -> SearchSnapshot:  # noqa: ARG001 - provider/model_id kept for call-site symmetry
    response = client.post(
        "/v1/search",
        {
            "query": query,
            "provider": "gemini-grounded-search",
            "search_type": "web",
            "max_results": 10,
            "time_range": "month",
        },
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
    instructor_call=None,
    previous_limit: float | None = None,
) -> QuotaResearchResult:
    query = build_quota_query(provider, model_id, today=today)
    try:
        snapshot = run_quota_search(client, provider=provider, model_id=model_id, query=query)
        claims = _extract_claims(snapshot, instructor_call=instructor_call, previous_limit=previous_limit)
        rule = activate_summary_rule(
            claims[0],
            summary_confidence_cap=summary_confidence_cap,
            previous_limit=previous_limit,
            axes=claims,
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


def resolve_noauth_quota(
    *,
    provider: str,
    model_id: str,
    quota_rules: dict[tuple[str, str], ActiveQuotaRule],
    provider_models: dict[str, tuple[str, ...]],
    aliases: dict[str, str] | None = None,
) -> NoAuthQuotaResolution:
    aliases = NOAUTH_QUOTA_ALIASES if aliases is None else aliases
    alias_provider = aliases.get(provider)
    if alias_provider:
        rule = quota_rules.get((alias_provider, model_id))
        if rule is None:
            return _calibration_required(provider=provider, model_id=model_id, status="alias_quota_missing")
        return NoAuthQuotaResolution(
            provider=provider,
            model_id=model_id,
            status="shared_capacity",
            usable=True,
            rule=rule,
            quota_source_provider=alias_provider,
            model_source_provider=alias_provider,
            shared_with=alias_provider,
            model_ids=provider_models.get(alias_provider, ()),
            independence_status="assumed_shared",
            counted_as_independent=False,
        )

    rule = quota_rules.get((provider, model_id))
    if rule is not None:
        return NoAuthQuotaResolution(
            provider=provider,
            model_id=model_id,
            status="active",
            usable=True,
            rule=rule,
            quota_source_provider=provider,
            model_source_provider=provider,
            model_ids=provider_models.get(provider, ()),
            independence_status="confirmed",
            counted_as_independent=True,
        )

    return _calibration_required(provider=provider, model_id=model_id)


def promote_noauth_calibration(
    *,
    provider: str,
    model_id: str,
    evidence: NoAuthCalibrationEvidence,
) -> NoAuthQuotaResolution:
    if not _complete_calibration(evidence):
        return _calibration_required(provider=provider, model_id=model_id)
    if evidence.inferred_limit is None:
        return _calibration_required(provider=provider, model_id=model_id)
    claim = validate_claim(
        QuotaClaim(
            metric="tokens",
            amount=float(evidence.inferred_limit),
            window=str(evidence.reset_window),
            evidence=list(evidence.evidence),
            hard_stop=bool(evidence.hard_stop),
        )
    )
    return NoAuthQuotaResolution(
        provider=provider,
        model_id=model_id,
        status="active",
        usable=True,
        rule=ActiveQuotaRule(
            claim=claim,
            confidence=1.0,
            activated_by="operator_observed_omniroute_usage",
            capacity_class="calibrated",
            safe_mode=False,
            axes=(claim,),
        ),
        quota_source_provider=provider,
        model_source_provider=provider,
        model_ids=(model_id,),
        independence_status="confirmed",
        counted_as_independent=True,
    )


def _calibration_required(
    *,
    provider: str,
    model_id: str,
    status: str = "calibration_required",
) -> NoAuthQuotaResolution:
    return NoAuthQuotaResolution(
        provider=provider,
        model_id=model_id,
        status=status,
        usable=False,
        action=NOAUTH_CALIBRATION_ACTION,
    )


def _complete_calibration(evidence: NoAuthCalibrationEvidence) -> bool:
    return (
        evidence.observed_tokens is not None
        and evidence.observed_tokens > 0
        and evidence.inferred_limit is not None
        and evidence.inferred_limit > 0
        and evidence.reset_window in VALID_WINDOWS
        and evidence.hard_stop is True
        and bool(evidence.evidence)
    )


def _extract_claims(
    snapshot: SearchSnapshot, *, instructor_call, previous_limit: float | None = None
) -> tuple[QuotaClaim, ...]:
    if instructor_call is not None:
        try:
            return (
                _capacity_claim(
                    run_quota_inspector(
                        instructor_call,
                        _quota_inspector_prompt(snapshot),
                        previous_limit=previous_limit,
                    )
                ),
            )
        except QuotaResearchError:
            raise
        except Exception:
            pass
    return extract_summary_claims(snapshot)


def _quota_inspector_prompt(snapshot: SearchSnapshot) -> str:
    return "\n".join(
        [
            snapshot.query,
            snapshot.answer_text,
            *snapshot.evidence_urls,
        ]
    )


def resolve_quota_range(low: float, high: float, *, previous_limit: float | None) -> float:
    if low > high:
        raise ValueError("quota range low must be <= high")
    if previous_limit is None:
        return low
    return min(max(previous_limit, low), high)


def extract_summary_claim(snapshot: SearchSnapshot) -> QuotaClaim:
    return extract_summary_claims(snapshot)[0]


def extract_summary_claims(snapshot: SearchSnapshot) -> tuple[QuotaClaim, ...]:
    hard_stop = "hard stop" in snapshot.answer_text.lower()
    claims = tuple(
        _capacity_claim(
            QuotaClaim(
                metric=metric,
                amount=amount,
                window=window,
                evidence=list(snapshot.evidence_urls) or ["summary"],
                hard_stop=hard_stop,
            )
        )
        for metric, amount, window in _extract_axes(snapshot.answer_text)
    )
    if not claims:
        raise QuotaResearchError("quota_research", "missing_capacity_axis")
    return claims


def run_quota_inspector(call_instructor, prompt: str, *, previous_limit: float | None = None) -> QuotaClaim:
    site = LlmSiteConfig(
        name="quota-research-inspector",
        prompt_path=QUOTA_INSPECTOR_PROMPT,
        max_prompt_chars=7000,
    )
    response = _complete_quota_claim(
        call_instructor,
        site=site,
        context={
            "provider": "unknown",
            "provider_model_id": "unknown",
            "source_type": "search_summary",
            "source_url": "",
            "text": prompt,
            "previous_limit": "unknown" if previous_limit is None else str(previous_limit),
        },
    )
    return validate_claim(
        QuotaClaim(
            metric=response.metric,
            amount=response.amount,
            window=response.window,
            evidence=response.evidence,
            hard_stop=response.hard_stop,
        )
    )


def _complete_quota_claim(call_instructor, *, site: LlmSiteConfig, context: dict[str, object]) -> QuotaClaimResponse:
    if hasattr(call_instructor, "complete"):
        return call_instructor.complete(site=site, context=context, response_model=QuotaClaimResponse)
    return complete_with_adapter(
        call_instructor,
        site=site,
        context=context,
        response_model=QuotaClaimResponse,
    )


def _capacity_claim(claim: QuotaClaim) -> QuotaClaim:
    claim = validate_claim(claim)
    if claim.metric == "requests" and claim.window in {"minute", "hour"}:
        raise QuotaResearchError("quota_research", "reactive_rate_gate")
    return claim


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
    match = re.search(r"\b(\d+(?:[,\d]*)(?:\.\d+)?)\s+(?:requests?|tokens?)\b", text, re.IGNORECASE)
    if not match:
        raise QuotaResearchError("quota_research", "missing_amount")
    return _parse_amount(match.group(1))


def _extract_window(text: str) -> str:
    lowered = text.lower()
    for window in ("minute", "hour", "day", "month"):
        if f"per {window}" in lowered or f"/{window}" in lowered:
            return window
    raise QuotaResearchError("quota_research", "missing_window")


def _extract_axes(text: str) -> tuple[tuple[str, float, str], ...]:
    axes: list[tuple[str, float, str]] = []
    pattern = re.compile(
        r"\b(?P<amount>\d+(?:[,\d]*)(?:\.\d+)?)\s+"
        r"(?P<metric>requests?|tokens?)\s*(?:per|/)\s*"
        r"(?P<window>minute|hour|day|month)\b",
        re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        metric = "tokens" if match.group("metric").lower().startswith("token") else "requests"
        window = match.group("window").lower()
        # AICODE-NOTE: sub-day request limits are reactive OmniRoute rate gates;
        # only cumulative budgets become planning capacity axes.
        if metric == "requests" and window in {"minute", "hour"}:
            continue
        axes.append((metric, _parse_amount(match.group("amount")), window))
    if not axes:
        _extract_amount(text)
        _extract_window(text)
    return tuple(axes)


def _parse_amount(value: str) -> float:
    return float(value.replace(",", ""))


def activate_summary_rule(
    claim: QuotaClaim,
    *,
    summary_confidence_cap: float,
    previous_limit: float | None = None,
    axes: tuple[QuotaClaim, ...] = (),
) -> ActiveQuotaRule:
    validate_claim(claim)
    safe_mode = previous_limit is not None and claim.amount < previous_limit
    return ActiveQuotaRule(
        claim=claim,
        confidence=summary_confidence_cap,
        activated_by="summary",
        capacity_class="opportunistic",
        safe_mode=safe_mode,
        axes=tuple(validate_claim(axis) for axis in (axes or (claim,))),
    )
