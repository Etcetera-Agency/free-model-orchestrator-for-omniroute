from dataclasses import dataclass


@dataclass(frozen=True)
class WebCookieEndpoint:
    id: str
    model: str
    source: str
    auto_discovered: bool = False


@dataclass(frozen=True)
class ProbeOutcome:
    passed: bool
    confirmed_capabilities: dict[str, bool]


@dataclass(frozen=True)
class AllocationPolicy:
    fallback_only: bool
    primary_allowed: bool
    guaranteed_capacity: float
    budget_type: str


def source_web_cookie_endpoints(
    *,
    connections: list[dict],
    static: list[dict],
    manual: list[dict],
    previous: list[dict],
    daily_refresh: bool,
) -> list[WebCookieEndpoint]:
    endpoints = []
    for source, items in (("connection", connections), ("static", static), ("manual", manual), ("previous", previous)):
        for item in items:
            if source == "connection" and item.get("auth_type") != "web_cookie":
                continue
            endpoints.append(WebCookieEndpoint(id=item["id"], model=item["model"], source=source))
    return endpoints


def default_web_cookie_capabilities() -> dict[str, bool]:
    return {
        "text_chat": True,
        "tool_calling": False,
        "structured_output": False,
        "vision": False,
        "files": False,
        "audio": False,
    }


def web_cookie_role_eligible(*, required_capabilities: set[str], confirmed_capabilities: dict[str, bool]) -> bool:
    return all(confirmed_capabilities.get(capability) is True for capability in required_capabilities)


def web_cookie_text_probe(response_text: str, requested_capability: str | None = None) -> ProbeOutcome:
    lowered = response_text.lower()
    passed = bool(response_text.strip()) and "login" not in lowered and "challenge" not in lowered and "<html" not in lowered
    capabilities = default_web_cookie_capabilities()
    if passed and requested_capability:
        capabilities[requested_capability] = True
    return ProbeOutcome(passed=passed, confirmed_capabilities=capabilities)


def check_session_health(session: dict) -> str:
    return "unavailable" if session.get("expired") or session.get("challenge") else "available"


def web_cookie_allocation_policy(*, quota_known: bool, primary_override: bool) -> AllocationPolicy:
    return AllocationPolicy(
        fallback_only=not primary_override,
        primary_allowed=primary_override,
        guaranteed_capacity=1 if quota_known else 0,
        budget_type="guaranteed" if quota_known else "opportunistic",
    )
