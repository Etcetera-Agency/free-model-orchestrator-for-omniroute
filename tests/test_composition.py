from pathlib import Path

import pytest

from fmo.bootstrap import build_startup_config
from fmo.composition import build_canonical_stages, compose_runtime
from fmo.db import MigrationRunner
from fmo.pipeline import CANONICAL_STAGE_NAMES


def valid_env(**overrides):
    values = {
        "OMNIROUTE_URL": "https://omniroute.test",
        "DATABASE_URL": "postgresql://user:pass@localhost:5432/fmo",
        "HERMES_INVENTORY_MODE": "filesystem",
        "HERMES_HOME": "/tmp/hermes",
        "HERMES_AGENTS_PATH": "/tmp/hermes/agents",
        "HERMES_ROUTINES_PATH": "/tmp/hermes/routines",
        "HERMES_INVENTORY_CRON": "0 4 * * *",
    }
    values.update(overrides)
    return values


@pytest.mark.spec("runtime-bootstrap::Production dispatch executes a real stage")
def test_canonical_stage_list_matches_pipeline_order():
    stages = build_canonical_stages(metadata_sync=lambda **_kwargs: None)

    assert [stage.name for stage in stages] == CANONICAL_STAGE_NAMES


@pytest.mark.spec("runtime-bootstrap::Production dispatch executes a real stage")
def test_composed_runner_surfaces_stage_failure(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    config = build_startup_config(valid_env(DATABASE_URL=postgres_url))
    runtime = compose_runtime(config, metadata_sync=lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")))

    result = runtime.run_command("sync-metadata", object())

    assert result.exit_code == 4
    assert result.error_reason == "boom"


@pytest.mark.spec("runtime-bootstrap::Production dispatch executes a real stage")
def test_production_sync_metadata_uses_composed_stage(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    config = build_startup_config(valid_env(DATABASE_URL=postgres_url))
    calls = []
    runtime = compose_runtime(config, metadata_sync=lambda **kwargs: calls.append(kwargs))

    result = runtime.run_command("sync-metadata", object())

    assert result.exit_code == 0
    assert calls == [{"dry_run": False}]
