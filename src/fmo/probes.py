from dataclasses import dataclass

PROBE_ALLOWED_ACCESS = {"free_unlimited", "free_quota_available", "free_promotional_available"}


@dataclass(frozen=True)
class ProbeResult:
    passed: bool
    suites: tuple[str, ...]


def should_probe(access_status: str, *, reserved_capacity: bool) -> bool:
    return access_status in PROBE_ALLOWED_ACCESS and reserved_capacity


def probe_suites(capabilities: dict[str, bool]) -> tuple[str, ...]:
    suites = ["basic_text"]
    for capability, suite in (
        ("structured_output", "structured_output"),
        ("tools", "tool_calling"),
        ("vision", "vision"),
    ):
        if capabilities.get(capability):
            suites.append(suite)
    return tuple(suites)


def probe_endpoint(client, *, provider: str, model: str, capabilities: dict[str, bool]) -> ProbeResult:
    del provider
    suites = probe_suites(capabilities)
    response = client.post(
        "/v1/chat/completions",
        {
            "model": model,
            "messages": [{"role": "user", "content": "Return exactly ok"}],
            "max_tokens": 2,
            "temperature": 0,
            # AICODE-NOTE: Nvidia rejects OmniRoute-injected stream_options
            # unless stream=true; probes intentionally consume SSE text.
            "stream": True,
        },
        headers={"X-OmniRoute-No-Cache": "true"},
    )
    return ProbeResult(
        passed=_probe_response_status(response) == 200 and _probe_content_usable(_probe_response_content(response)),
        suites=suites,
    )


def _probe_response_status(response: dict) -> int:
    return int(response.get("status_code") or 200)


def _probe_response_content(response: dict) -> object:
    if "content" in response:
        return response.get("content")
    choices = response.get("choices")
    if not isinstance(choices, list):
        return ""
    parts = []
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message") or {}
        if isinstance(message, dict) and message.get("content"):
            parts.append(str(message["content"]))
    return "".join(parts)


def _probe_content_usable(content: object) -> bool:
    if not content:
        return False
    text = str(content).lower()
    return not any(
        phrase in text
        for phrase in (
            "prevent abuse of free resources",
            "accounts that have not been recharged",
            "increase the free quota after recharging",
        )
    )


def handle_probe_error(status_code: int) -> tuple[str, str]:
    if status_code == 402:
        return ("exclude", "quota_research")
    if status_code == 429:
        return ("quota_manager", "no_retry")
    if status_code in {401, 403}:
        return ("auth_degraded", "no_retry")
    if status_code >= 500:
        return ("retry", "provider_5xx")
    return ("failed", "unknown")
