from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from fmo.bootstrap import bootstrap_and_dispatch, build_startup_config
from fmo.cli import main
from fmo.db import MigrationRunner
from fmo.persistence import Database, Repository
from tests._composition_support import seed_apply_ready_diff


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


@pytest.mark.spec("combo-applier::Failing guard input blocks apply")
def test_apply_entrypoint_fails_closed_when_guard_inputs_missing(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))

    exit_code = main(
        ["apply"],
        env=valid_env(DATABASE_URL=postgres_url),
        health_check=lambda: {"ok": True},
    )

    repository = Repository(Database(postgres_url))
    with repository.database.transaction() as transaction:
        assert repository.runs.list(transaction) == []
    assert exit_code == 5


@pytest.mark.spec("combo-applier::Diff-scoped request-window guard allows apply")
def test_apply_entrypoint_uses_diff_scoped_apply_safety(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    endpoint_id = seed_apply_ready_diff(
        repository,
        role_id="routing_fast",
        combo_id="fmo-routing_fast",
        before=["old-endpoint"],
        after_model_id="request-window-model",
    )
    with repository.database.transaction() as transaction:
        transaction.execute(
            """
            UPDATE endpoint_access_states
            SET effective_remaining = '{"requests": 40}'::jsonb,
                reset_at = now() + interval '1 minute',
                evidence = '{
                  "quota_delegated_to": "omniroute",
                  "safety_buffer": 1
                }'::jsonb
            WHERE endpoint_id = %(endpoint_id)s
            """,
            {"endpoint_id": endpoint_id},
        )
        transaction.execute(
            """
            INSERT INTO endpoint_probes (
              endpoint_id, suite_version, probe_type, request_hash, passed, http_status,
              started_at, finished_at, details
            )
            VALUES (
              %(endpoint_id)s, 'production-v1', 'basic', 'old-failed-probe', false, 500,
              now() - interval '1 hour', now() - interval '1 hour', '{}'::jsonb
            )
            """,
            {"endpoint_id": endpoint_id},
        )
    calls = []

    exit_code = main(
        ["apply"],
        env=valid_env(DATABASE_URL=postgres_url),
        health_check=lambda: {"ok": True},
        dispatcher=lambda argv, preconditions_ok, config: calls.append((argv, preconditions_ok)) or 0,
    )

    assert exit_code == 0
    assert calls == [(["apply"], True)]


@pytest.mark.spec("runtime-bootstrap::Entrypoint uses real arguments")
def test_apply_entrypoint_uses_apply_adapter_guard(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    _seed_healthy_apply_guard(postgres_url)

    exit_code = main(
        ["apply"],
        env=valid_env(DATABASE_URL=postgres_url),
        health_check=lambda: {"ok": True},
    )

    repository = Repository(Database(postgres_url))
    with repository.database.transaction() as transaction:
        runs = repository.runs.list(transaction)
    assert exit_code == 5
    assert len(runs) == 1
    assert runs[0]["status"] == "unsafe_to_apply"
    assert [stage["name"] for stage in runs[0]["error_json"]["stages"]] == ["apply"]


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
        role = repository.roles.upsert(
            transaction,
            role_id="coder",
            requirements={"minimum_context_window": 8192},
            expected_load={"requests": 1},
            criticality=5,
        )
        repository.allocation_plans.upsert(
            transaction,
            role_id=role["id"],
            status="planned",
            targets=[],
            constraint_report={"ok": True},
            input_state_hash="plan-key",
        )

    exit_code = main(
        ["explain-role", "--role", "coder"],
        env=valid_env(DATABASE_URL=postgres_url),
        health_check=lambda: {"ok": True},
    )

    assert exit_code == 0


def _seed_healthy_apply_guard(postgres_url):
    repository = Repository(Database(postgres_url))
    with repository.database.transaction() as transaction:
        provider = repository.providers.upsert(
            transaction,
            omniroute_instance_id="local",
            omniroute_provider_id="openai",
            provider_type="api",
        )
        account = repository.provider_accounts.upsert(
            transaction,
            provider_id=provider["id"],
            omniroute_connection_id="conn-openai",
        )
        endpoint = repository.provider_endpoints.upsert(
            transaction,
            provider_account_id=account["id"],
            provider_model_id="gpt-test",
            lifecycle_status="active",
            access_status="free_quota_available",
        )
        role = repository.roles.upsert(
            transaction,
            role_id="coder",
            requirements={"minimum_context_window": 8192},
            expected_load={"requests": 1},
            criticality=5,
        )
        repository.combo_snapshots.upsert(
            transaction,
            role_id=role["id"],
            state_hash="current-key",
            state_json={"models": ["openai/gpt-test"]},
            phase="current",
        )
        repository.allocation_plans.upsert(
            transaction,
            role_id=role["id"],
            status="planned",
            targets=[{"endpoint_id": str(endpoint["id"])}],
            constraint_report={"ok": True, "quota_safe": True},
            input_state_hash="plan-key",
        )
        # Keep the seeded smoke probe inside the apply staleness window
        # (APPLY_STAGE_EVIDENCE_MAX_AGE = 1 day) so the guard stays "healthy"
        # regardless of when the suite runs.
        probe_started = datetime.now(UTC) - timedelta(minutes=1)
        repository.probes.record(
            transaction,
            endpoint_id=endpoint["id"],
            suite_version="v1",
            probe_type="smoke",
            request_hash="probe-key",
            passed=True,
            started_at=probe_started.isoformat(),
            finished_at=(probe_started + timedelta(seconds=1)).isoformat(),
        )
