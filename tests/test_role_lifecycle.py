from datetime import datetime, timedelta, timezone

import pytest

from fmo.hermes_inventory import (
    InspectorForecast,
    assemble_inspector_prompt,
    inventory_diff,
    normalize_command_inventory,
    normalize_filesystem_inventory,
    normalize_http_inventory,
    run_inspector,
    should_run_full_inventory,
)
from fmo.role_lifecycle import reconcile_roles


@pytest.mark.spec("hermes-inventory::Missing required env")
def test_adapters_normalize_samples_and_missing_env_fails():
    sample = {"roles": [{"role": "research_scout", "consumer_type": "cron_job", "consumer": "daily", "cadence": "0 4 * * *", "calls_per_run": 2}]}
    assert normalize_filesystem_inventory(sample, env={"HERMES_HOME": "/tmp"}).consumers[0].consumer_type == "cron_job"
    assert normalize_command_inventory(sample, env={"HERMES_INVENTORY_COMMAND": "hermes inventory"}).consumers[0].role_id == "research_scout"
    assert normalize_http_inventory(sample, env={"HERMES_INVENTORY_URL": "http://localhost"}).consumers[0].calls_per_run == 2
    with pytest.raises(ValueError):
        normalize_filesystem_inventory(sample, env={})


@pytest.mark.spec("hermes-inventory::Unknown role observed")
def test_daily_inventory_records_all_consumer_types_and_unknown_role_full_inventory():
    sample = {
        "roles": [
            {"role": "r", "consumer_type": "agent_profile", "consumer": "p", "cadence": "manual", "calls_per_run": 1},
            {"role": "r", "consumer_type": "cron_job", "consumer": "c", "cadence": "daily", "calls_per_run": 2},
            {"role": "r", "consumer_type": "webhook", "consumer": "w", "cadence": "observed", "calls_per_run": 3},
            {"role": "r", "consumer_type": "service", "consumer": "s", "cadence": "continuous", "calls_per_run": 4},
        ]
    }
    inventory = normalize_command_inventory(sample, env={"HERMES_INVENTORY_COMMAND": "cmd"})
    assert {consumer.consumer_type for consumer in inventory.consumers} == {"agent_profile", "cron_job", "webhook", "service"}
    assert should_run_full_inventory(observed_role="new", known_roles={"r"}) == "full"


@pytest.mark.spec("hermes-inventory::Schedule changed")
def test_inventory_diff_marks_forecast_stale_and_material_allocation_gate():
    old = normalize_command_inventory({"roles": [{"role": "r", "consumer_type": "cron_job", "consumer": "c", "cadence": "daily", "calls_per_run": 1}]}, env={"HERMES_INVENTORY_COMMAND": "cmd"})
    new = normalize_command_inventory({"roles": [{"role": "r", "consumer_type": "cron_job", "consumer": "c", "cadence": "hourly", "calls_per_run": 1}]}, env={"HERMES_INVENTORY_COMMAND": "cmd"})
    diff = inventory_diff(old, new)
    assert diff.forecast_stale is True
    assert diff.run_inspector is True
    assert diff.rebuild_combo(material_allocation_changed=False) is False


@pytest.mark.spec("hermes-inventory::Inspector does not inspect")
def test_inspector_prompt_and_scope_no_secret_or_file_reads():
    inventory = normalize_command_inventory({"roles": [{"role": "r", "consumer_type": "webhook", "consumer": "w", "cadence": "observed", "calls_per_run": 3}]}, env={"HERMES_INVENTORY_COMMAND": "cmd"})
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
