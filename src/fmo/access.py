from dataclasses import dataclass


@dataclass(frozen=True)
class AccessDecision:
    status: str
    reason_code: str


def classify_access(evidence: dict) -> AccessDecision:
    if evidence.get("disabled") or evidence.get("removed") or evidence.get("permanently_broken"):
        return AccessDecision("unavailable", "endpoint_unavailable")
    if evidence.get("manual_deny") or evidence.get("live_paid_charge"):
        return AccessDecision("paid_only_excluded", "trusted_paid_evidence")
    if evidence.get("price_input") == 0 and evidence.get("price_output") == 0 and not evidence.get("paid_component"):
        return AccessDecision("free_unlimited", "zero_price")
    if evidence.get("quota_rule"):
        if _has_free_quota_preconditions(evidence):
            if evidence["remaining"] <= evidence.get("safety_buffer", 0):
                return AccessDecision("free_quota_exhausted", "safety_buffer_exhausted")
            return AccessDecision("free_quota_available", "quota_rule_remaining")
        return AccessDecision("unknown_excluded", "missing_quota_precondition")
    if evidence.get("promotion_active"):
        return AccessDecision("free_promotional_available", "promotion_active")
    if evidence.get("promotion_expired"):
        return AccessDecision("free_promotional_expired", "promotion_expired")
    return AccessDecision("unknown_excluded", "fail_closed")


def _has_free_quota_preconditions(evidence: dict) -> bool:
    return (
        all(evidence.get(key) is not None for key in ("limit", "remaining", "reset_at"))
        and evidence.get("hard_stop") is True
    )
