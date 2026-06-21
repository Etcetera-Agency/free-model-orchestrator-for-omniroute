from datetime import datetime, timedelta, timezone

import pytest

from fmo.hermes_inventory import (
    InspectorForecast,
    assemble_inspector_prompt,
    build_hermes_inventory,
    inventory_diff,
    normalize_filesystem_inventory,
    run_inspector,
)
from fmo.role_lifecycle import reconcile_roles
from _fixtures import hermes_fixture_path, load_hermes_fixture


def _profiles_with_config_paths(tmp_path):
    payload = load_hermes_fixture("profiles.json")
    home = tmp_path / "hermes"
    default_dir = home
    research_dir = home / "profiles" / "research"
    default_dir.mkdir(parents=True)
    research_dir.mkdir(parents=True)
    (default_dir / "config.yaml").write_text(hermes_fixture_path("config.default.yaml").read_text())
    (research_dir / "config.yaml").write_text(hermes_fixture_path("config.research.yaml").read_text())
    payload["profiles"][0]["path"] = str(default_dir)
    payload["profiles"][1]["path"] = str(research_dir)
    return payload


@pytest.mark.spec("hermes-inventory::Missing required env")
def test_adapters_normalize_samples_and_missing_env_fails():
    with pytest.raises(ValueError):
        normalize_filesystem_inventory({}, env={})


@pytest.mark.spec("hermes-inventory::Mixed consumers recorded")
def test_daily_inventory_records_all_consumer_types(tmp_path):
    inventory = build_hermes_inventory(
        cron_jobs=load_hermes_fixture("cron_jobs.json"),
        webhook_subscriptions=load_hermes_fixture("webhook_subscriptions.json"),
        profiles=_profiles_with_config_paths(tmp_path),
    )

    assert {consumer.consumer_type for consumer in inventory.consumers} >= {"agent_profile", "cron_job", "webhook", "service"}


@pytest.mark.spec("hermes-inventory::Schedule changed")
def test_inventory_diff_marks_forecast_stale_and_material_allocation_gate():
    old = build_hermes_inventory(
        cron_jobs=load_hermes_fixture("cron_jobs.json"),
        webhook_subscriptions=load_hermes_fixture("webhook_subscriptions.json"),
        profiles=[],
    )
    changed_cron_jobs = load_hermes_fixture("cron_jobs.json")
    changed_cron_jobs["jobs"][0]["schedule"] = {"kind": "interval", "minutes": 60, "display": "hourly"}
    new = build_hermes_inventory(
        cron_jobs=changed_cron_jobs,
        webhook_subscriptions=load_hermes_fixture("webhook_subscriptions.json"),
        profiles=[],
    )
    diff = inventory_diff(old, new)
    assert diff.forecast_stale is True
    assert diff.run_inspector is True
    assert diff.rebuild_combo(material_allocation_changed=False) is False


@pytest.mark.spec("hermes-inventory::Inspector does not inspect")
@pytest.mark.spec("hermes-inventory::Inspector output")
def test_inspector_prompt_and_scope_no_secret_or_file_reads():
    inventory = build_hermes_inventory(
        cron_jobs=load_hermes_fixture("cron_jobs.json"),
        webhook_subscriptions=load_hermes_fixture("webhook_subscriptions.json"),
        profiles=load_hermes_fixture("profiles.json"),
    )
    prompt = assemble_inspector_prompt(inventory, changes=["cadence changed"], secrets={"HERMES_INVENTORY_TOKEN": "secret"})
    forecast = run_inspector(lambda prompt: {"role": "r", "expected_calls": 9, "average_input_tokens": 100, "average_output_tokens": 20, "confidence": "low"}, prompt)
    assert "secret" not in prompt
    assert isinstance(forecast, InspectorForecast)
    assert forecast.model_choice is None
    assert forecast.quota_change is None


@pytest.mark.spec("dynamic-role-lifecycle::Role disappears once")
@pytest.mark.spec("dynamic-role-lifecycle::Role reappears within grace")
@pytest.mark.spec("dynamic-role-lifecycle::Brand-new role")
def test_reconcile_retire_grace_reactivate_and_new_role_bootstrap():
    now = datetime.now(timezone.utc)
    roles = {
        "old": {"status": "active", "combo": ["e1"], "recent_usage": 0},
        "back": {"status": "retiring", "missing_since": now - timedelta(days=1), "combo": ["e2"], "recent_usage": 1},
    }
    result = reconcile_roles(roles, desired_roles={"back", "new"}, now=now, grace_period=timedelta(days=7))
    assert result["old"]["status"] == "retiring"
    assert result["old"]["combo"] == ["e1"]
    assert result["back"]["status"] == "active"
    assert result["back"]["missing_since"] is None
    assert result["new"]["status"] == "bootstrap_pending"
    assert result["new"]["policy_template"]
    assert result["new"]["cold_start_demand"] > 0
