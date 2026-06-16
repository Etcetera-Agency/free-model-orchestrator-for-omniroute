from fmo.cli import EXIT_CODES, parse_args, run_cli
from fmo.web_cookie import (
    check_session_health,
    default_web_cookie_capabilities,
    source_web_cookie_endpoints,
    web_cookie_allocation_policy,
    web_cookie_role_eligible,
    web_cookie_text_probe,
)


def test_web_cookie_sources_no_daily_auto_discovery():
    endpoints = source_web_cookie_endpoints(
        connections=[{"id": "c1", "auth_type": "web_cookie", "model": "m1"}],
        static=[{"id": "s1", "model": "m2"}],
        manual=[{"id": "m1", "model": "m3"}],
        previous=[{"id": "p1", "model": "m4"}],
        daily_refresh=True,
    )
    assert {endpoint.source for endpoint in endpoints} == {"connection", "static", "manual", "previous"}
    assert all(endpoint.auto_discovered is False for endpoint in endpoints)


def test_capability_gate_default_text_only_and_raise_after_probe():
    capabilities = default_web_cookie_capabilities()
    assert web_cookie_role_eligible(required_capabilities={"text_chat"}, confirmed_capabilities=capabilities) is True
    assert web_cookie_role_eligible(required_capabilities={"tool_calling"}, confirmed_capabilities=capabilities) is False
    raised = web_cookie_text_probe("plain answer", requested_capability="structured_output")
    assert raised.confirmed_capabilities["structured_output"] is True


def test_basic_text_probe_and_session_health():
    assert web_cookie_text_probe("plain answer").passed is True
    assert web_cookie_text_probe("<html>login challenge</html>").passed is False
    assert check_session_health({"expired": True}) == "unavailable"


def test_fallback_only_unknown_quota_opportunistic():
    policy = web_cookie_allocation_policy(quota_known=False, primary_override=False)
    override = web_cookie_allocation_policy(quota_known=True, primary_override=True)
    assert policy.fallback_only is True
    assert policy.guaranteed_capacity == 0
    assert policy.budget_type == "opportunistic"
    assert override.primary_allowed is True


def test_cli_commands_flags_exit_codes_and_dry_run_no_combo_test():
    args = parse_args(["apply", "--dry-run", "--role", "research_scout", "--json"])
    assert args.command == "apply"
    assert args.dry_run is True
    unsafe = run_cli(["apply"], preconditions_ok=False)
    dry = run_cli(["allocate", "--dry-run"], preconditions_ok=True)
    aa = parse_args(["aa-index", "status"])
    assert EXIT_CODES["unsafe_to_apply"] == 5
    assert unsafe.exit_code == 5
    assert unsafe.changed is False
    assert dry.combo_test_called is False
    assert aa.command == "aa-index"
    assert aa.aa_command == "status"
