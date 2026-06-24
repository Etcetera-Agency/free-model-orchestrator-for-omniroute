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
