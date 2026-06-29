from pathlib import Path

import pytest

from fmo.bootstrap import bootstrap_and_dispatch, build_startup_config
from fmo.cli import main
from fmo.db import MigrationRunner
from fmo.persistence import Database, Repository


def valid_env(**overrides):
    values = {
        "OMNIROUTE_URL": "https://omniroute.test",
        "OMNIROUTE_API_KEY": "test-key",
        "DATABASE_URL": "postgresql://user:pass@localhost:5432/fmo",
        "HERMES_INVENTORY_MODE": "filesystem",
        "HERMES_HOME": "/tmp/hermes",
        "HERMES_AGENTS_PATH": "/tmp/hermes/agents",
        "HERMES_ROUTINES_PATH": "/tmp/hermes/routines",
        "HERMES_INVENTORY_CRON": "0 4 * * *",
    }
    values.update(overrides)
    return values


@pytest.mark.spec("runtime-bootstrap::Invalid environment fails before running")
@pytest.mark.parametrize(
    "env_patch",
    [
        {"OMNIROUTE_URL": "ftp://omniroute.test"},
        {"OMNIROUTE_API_KEY": ""},
        {"DATABASE_URL": ""},
        {"HERMES_INVENTORY_MODE": "bad"},
        {"HERMES_INVENTORY_CRON": "bad cron"},
    ],
)
def test_invalid_env_maps_to_exit_3_and_does_not_dispatch(env_patch):
    calls = []

    exit_code = bootstrap_and_dispatch(
        ["full"],
        env=valid_env(**env_patch),
        health_check=lambda: {"ok": True},
        dispatcher=lambda argv, preconditions_ok, config: calls.append((argv, preconditions_ok)) or 0,
    )

    assert exit_code == 3
    assert calls == []


@pytest.mark.spec("llm-runtime::Missing LLM provider config fails closed")
def test_missing_llm_provider_config_fails_before_dispatch():
    calls = []

    exit_code = bootstrap_and_dispatch(
        ["full"],
        env=valid_env(OMNIROUTE_API_KEY=""),
        health_check=lambda: {"ok": True},
        dispatcher=lambda argv, preconditions_ok, config: calls.append((argv, preconditions_ok)) or 0,
    )

    assert exit_code == 3
    assert calls == []


@pytest.mark.spec("runtime-bootstrap::Invalid environment fails before running")
def test_build_startup_config_reads_mode_specific_environment():
    filesystem = build_startup_config(valid_env())
    command = build_startup_config(
        valid_env(
            HERMES_INVENTORY_MODE="command",
            HERMES_HOME="",
            HERMES_AGENTS_PATH="",
            HERMES_ROUTINES_PATH="",
            HERMES_INVENTORY_COMMAND="hermes inventory",
        )
    )
    http = build_startup_config(
        valid_env(
            HERMES_INVENTORY_MODE="http",
            HERMES_HOME="",
            HERMES_AGENTS_PATH="",
            HERMES_ROUTINES_PATH="",
            HERMES_INVENTORY_URL="https://inventory.test",
        )
    )

    assert filesystem.hermes_home == "/tmp/hermes"
    assert command.hermes_inventory_command == "hermes inventory"
    assert http.hermes_inventory_url == "https://inventory.test"


@pytest.mark.spec("runtime-bootstrap::Health check precedes the pipeline")
def test_health_check_runs_before_dispatch():
    calls = []

    exit_code = bootstrap_and_dispatch(
        ["full"],
        env=valid_env(),
        health_check=lambda: calls.append("health") or {"ok": True},
        dispatcher=lambda argv, preconditions_ok, config: calls.append(("dispatch", argv, preconditions_ok)) or 0,
    )

    assert exit_code == 0
    assert calls == ["health", ("dispatch", ["full"], True)]


@pytest.mark.spec("runtime-bootstrap::Entrypoint uses real arguments")
def test_main_uses_real_argv_and_validation_state(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    calls = []

    exit_code = main(
        ["full", "--dry-run"],
        env=valid_env(DATABASE_URL=postgres_url),
        health_check=lambda: {"ok": True},
        dispatcher=lambda argv, preconditions_ok, config: calls.append((argv, preconditions_ok)) or 0,
    )

    assert exit_code == 0
    assert calls == [(["full", "--dry-run"], True)]


@pytest.mark.spec("runtime-bootstrap::Production dispatch executes a real stage")
def test_production_dispatch_composes_and_runs_stage_without_injected_runner(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))

    exit_code = main(
        ["scan-providers"],
        env=valid_env(DATABASE_URL=postgres_url),
        health_check=lambda: {"ok": True},
    )

    repository = Repository(Database(postgres_url))
    with repository.database.transaction() as transaction:
        runs = repository.runs.list(transaction)
    assert exit_code == 4
    assert len(runs) == 1
    assert runs[0]["status"] == "external_dependency_failed"
    assert [stage["name"] for stage in runs[0]["error_json"]["stages"]] == ["free-candidate-discovery"]


@pytest.mark.spec("runtime-bootstrap::Diagnostics read persisted state by default")
def test_production_dispatch_reads_diagnostics_without_injected_reader(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    with repository.database.transaction() as transaction:
        repository.roles.upsert(
            transaction,
            role_id="coder",
            requirements={"minimum_context_window": 8192},
            expected_load={"requests": 1},
            criticality=5,
        )

    exit_code = main(
        ["explain-role", "--role", "coder"],
        env=valid_env(DATABASE_URL=postgres_url),
        health_check=lambda: {"ok": True},
    )

    assert exit_code == 0
