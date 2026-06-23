from dataclasses import dataclass

PROBE_ALLOWED_ACCESS = {"free_unlimited", "free_quota_available", "free_promotional_available"}


@dataclass(frozen=True)
class ProbeResult:
    passed: bool
    suites: tuple[str, ...]


def should_probe(access_status: str, *, reserved_capacity: bool) -> bool:
    return access_status in PROBE_ALLOWED_ACCESS and reserved_capacity


def probe_endpoint(client, *, provider: str, model: str, capabilities: dict[str, bool]) -> ProbeResult:
    suites = ["basic_text"]
    for capability, suite in (
        ("structured_output", "structured_output"),
        ("tools", "tool_calling"),
        ("vision", "vision"),
    ):
        if capabilities.get(capability):
            suites.append(suite)
    response = client.post(
        f"/v1/providers/{provider}/chat/completions",
        {"model": model, "messages": [{"role": "user", "content": "Return ok"}]},
        headers={"X-OmniRoute-No-Cache": "true"},
    )
    return ProbeResult(passed=response["status_code"] == 200 and bool(response.get("content")), suites=tuple(suites))


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
