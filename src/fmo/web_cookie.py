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
    failure_mode: str | None = None


@dataclass(frozen=True)
class AllocationPolicy:
    fallback_only: bool
    primary_allowed: bool
    guaranteed_capacity: float
    budget_type: str
    allocation_weight: float


@dataclass(frozen=True)
class WebCookieSessionAcquisition:
    endpoint: WebCookieEndpoint
    source_id: str
    acquired: bool
    confirmed_usable: bool
    failure_mode: str | None
    confirmed_capabilities: dict[str, bool]
    allocation_policy: AllocationPolicy | None


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
    return classify_web_cookie_probe(session={}, response_text=response_text, requested_capability=requested_capability)


def check_session_health(session: dict) -> str:
    return "unavailable" if session.get("expired") or session.get("challenge") else "available"


def web_cookie_allocation_policy(*, quota_known: bool, primary_override: bool) -> AllocationPolicy:
    return AllocationPolicy(
        fallback_only=not primary_override,
        primary_allowed=primary_override,
        guaranteed_capacity=1 if quota_known else 0,
        budget_type="guaranteed" if quota_known else "opportunistic",
        allocation_weight=1.0 if quota_known else 0.1,
    )


def classify_web_cookie_probe(
    *,
    session: dict,
    response_text: str,
    http_status: int = 200,
    auth_type: str = "web_cookie",
    requested_capability: str | None = None,
) -> ProbeOutcome:
    capabilities = default_web_cookie_capabilities()
    failure_mode = _web_cookie_failure_mode(
        session=session,
        response_text=response_text,
        http_status=http_status,
        auth_type=auth_type,
    )
    if failure_mode is not None:
        return ProbeOutcome(passed=False, confirmed_capabilities=capabilities, failure_mode=failure_mode)
    if requested_capability:
        capabilities[requested_capability] = True
    return ProbeOutcome(passed=True, confirmed_capabilities=capabilities)


def acquire_web_cookie_sessions(
    *,
    endpoints: list[WebCookieEndpoint],
    configured_sources: list[dict],
    eligible_source_ids: set[str],
    probe_responses: list[dict],
    quota_known_by_endpoint: dict[str, bool] | None = None,
) -> list[WebCookieSessionAcquisition]:
    endpoint_by_id = {endpoint.id: endpoint for endpoint in endpoints}
    probe_by_endpoint = {probe["endpoint_id"]: probe for probe in probe_responses}
    quota_known_by_endpoint = quota_known_by_endpoint or {}
    acquisitions: list[WebCookieSessionAcquisition] = []

    for source in configured_sources:
        source_id = source["source_id"]
        endpoint = endpoint_by_id.get(source.get("endpoint_id"))
        if endpoint is None or source_id not in eligible_source_ids:
            continue

        probe = probe_by_endpoint.get(endpoint.id, {})
        outcome = classify_web_cookie_probe(
            session=source.get("session", {}),
            response_text=probe.get("response_text", ""),
            http_status=probe.get("http_status", 200),
            auth_type=source.get("auth_type", "web_cookie"),
            requested_capability=probe.get("requested_capability"),
        )
        policy = None
        if outcome.passed:
            policy = web_cookie_allocation_policy(
                quota_known=quota_known_by_endpoint.get(endpoint.id, False),
                primary_override=source.get("primary_override", False),
            )
        acquisitions.append(
            WebCookieSessionAcquisition(
                endpoint=endpoint,
                source_id=source_id,
                acquired=outcome.passed,
                confirmed_usable=outcome.passed,
                failure_mode=outcome.failure_mode,
                confirmed_capabilities=outcome.confirmed_capabilities,
                allocation_policy=policy,
            )
        )
    return acquisitions


def _web_cookie_failure_mode(*, session: dict, response_text: str, http_status: int, auth_type: str) -> str | None:
    if auth_type != "web_cookie":
        return "unsupported_auth"
    lowered = response_text.lower()
    if (
        session.get("expired")
        or http_status == 401
        or "session_expired" in _lower_markers(session)
        or "session expired" in lowered
        or "session_expired" in lowered
    ):
        return "expired"

    if session.get("challenge") or http_status == 403 or any(marker in lowered for marker in ("captcha", "challenge")):
        return "challenge"
    if any(marker in lowered for marker in ("login required", "sign in", "signin", "<html")):
        return "login_required"
    if not response_text.strip():
        return "login_required"
    return None


def _lower_markers(session: dict) -> str:
    markers = session.get("markers", [])
    if isinstance(markers, list):
        return " ".join(str(marker).lower() for marker in markers)
    return str(markers).lower()
