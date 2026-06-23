import threading
import time
from datetime import UTC, datetime
from pathlib import Path

import psycopg
import pytest
from psycopg.rows import dict_row

from fmo.db import MigrationRunner
from fmo.persistence import Database, Repository
from fmo.pipeline import PipelineRunResult
from fmo.scheduler import RunLockManager, Scheduler


@pytest.fixture()
def repository(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    return Repository(Database(postgres_url))


def _active_lock_index_definition(connection) -> str | None:
    row = connection.execute(
        """
        SELECT indexdef
        FROM pg_indexes
        WHERE schemaname = 'public'
          AND tablename = 'sync_runs'
          AND indexname = 'sync_runs_active_lock_name_idx'
        """
    ).fetchone()
    return row[0] if row else None


def _assert_active_lock_index(connection) -> None:
    index_definition = _active_lock_index_definition(connection)

    assert index_definition is not None
    assert "UNIQUE" in index_definition
    assert "WHERE" in index_definition
    assert "run_type = 'lock'::text" in index_definition
    assert "status = 'held'::text" in index_definition
    assert "finished_at IS NULL" in index_definition


@pytest.mark.spec("scheduler::Daily lock blocks a concurrent run")
@pytest.mark.spec("scheduler::Overlapping daily runs")
@pytest.mark.spec("scheduler::Concurrent start blocked by the lock")
def test_daily_lock_blocks_concurrent_run(repository):
    locks = RunLockManager(repository)

    first = locks.acquire("daily")
    second = locks.acquire("daily")
    first.release()
    third = locks.acquire("daily")
    third.release()

    assert first.acquired is True
    assert second.acquired is False
    assert third.acquired is True


@pytest.mark.spec("scheduler::Concurrent repository acquisition has one winner")
def test_repository_lock_acquire_is_atomic_across_connections(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    results = []

    with psycopg.connect(postgres_url, row_factory=dict_row) as first_connection:
        first_token = repository.locks.acquire(first_connection, "daily")

        def acquire_second_lock():
            with psycopg.connect(postgres_url, row_factory=dict_row) as second_connection:
                second_token = repository.locks.acquire(second_connection, "daily")
                second_connection.commit()
            results.append(second_token)

        second = threading.Thread(target=acquire_second_lock)
        second.start()
        time.sleep(0.2)
        first_connection.commit()
        second.join(timeout=5)

    assert second.is_alive() is False
    assert len(results) == 1
    assert [first_token, results[0]].count(None) == 1

    with psycopg.connect(postgres_url) as connection:
        active_lock_count = connection.execute(
            """
            SELECT count(*)
            FROM sync_runs
            WHERE run_type = 'lock'
              AND trigger = 'daily'
              AND status = 'held'
              AND finished_at IS NULL
            """
        ).fetchone()[0]

    assert active_lock_count == 1


def test_fresh_schema_has_active_lock_unique_index(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))

    with psycopg.connect(postgres_url) as connection:
        _assert_active_lock_index(connection)


def test_lock_index_migration_adds_active_lock_unique_index(postgres_url):
    migration = Path("reference/db/migrations/0008_v3.20_atomic_run_locks.sql")

    with psycopg.connect(postgres_url, autocommit=True) as connection:
        connection.execute(
            """
            CREATE TABLE sync_runs (
              id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
              run_type text NOT NULL,
              trigger text NOT NULL,
              status text NOT NULL,
              code_version text NOT NULL,
              config_hash text NOT NULL,
              omniroute_version text,
              started_at timestamptz NOT NULL DEFAULT now(),
              finished_at timestamptz,
              error_json jsonb
            )
            """
        )
        connection.execute(migration.read_text(encoding="utf-8"))
        _assert_active_lock_index(connection)


@pytest.mark.spec("scheduler::Lock released on failure")
def test_lock_context_releases_after_failure(repository):
    locks = RunLockManager(repository)

    with pytest.raises(RuntimeError, match="boom"):
        with locks.hold("combo-apply") as lock:
            assert lock.acquired is True
            raise RuntimeError("boom")

    assert locks.acquire("combo-apply").acquired is True


@pytest.mark.spec("scheduler::Daily lock blocks a concurrent run")
def test_provider_and_combo_locks_are_independent(repository):
    locks = RunLockManager(repository)

    provider_a = locks.acquire("provider-scan", scope="openai")
    provider_a_again = locks.acquire("provider-scan", scope="openai")
    provider_b = locks.acquire("provider-scan", scope="anthropic")
    combo = locks.acquire("combo-apply")

    assert provider_a.acquired is True
    assert provider_a_again.acquired is False
    assert provider_b.acquired is True
    assert combo.acquired is True


@pytest.mark.spec("scheduler::Scheduler fires at cron time")
@pytest.mark.spec("scheduler::Scheduled daily run")
@pytest.mark.spec("scheduler::Service fires the daily run")
@pytest.mark.spec("hermes-inventory::Daily run performs full inventory")
def test_scheduler_fires_full_pipeline_at_configured_cron(repository):
    calls = []

    def runner(trigger, run_type):
        calls.append((trigger, run_type))
        return PipelineRunResult(
            run_id="run-1",
            status="success",
            exit_code=0,
            changed=False,
            stage_results=[],
            skipped_stages=[],
        )

    scheduler = Scheduler(repository, cron="0 4 * * *", pipeline_runner=runner)

    cron_now = datetime.now(UTC).replace(hour=4, minute=0, second=0, microsecond=0)
    result = scheduler.tick(cron_now.isoformat())

    assert result.exit_code == 0
    assert calls == [("scheduled", "full")]


def _recalibration_scheduler(repository, calls):
    return Scheduler(
        repository,
        cron="0 4 * * *",
        pipeline_runner=lambda _trigger, _run_type: None,
        recalibration_cron="0 5 * * 0",
        recalibration_job=lambda: calls.append("recalibrate") or "done",
    )


@pytest.mark.spec("scheduler::Weekly recalibration fires")
def test_scheduler_fires_weekly_recalibration_at_configured_cron(repository):
    calls = []
    scheduler = _recalibration_scheduler(repository, calls)

    cron_now = datetime.now(UTC).replace(hour=5, minute=0, second=0, microsecond=0)
    result = scheduler.tick_recalibration(cron_now.isoformat())

    assert result == "done"
    assert calls == ["recalibrate"]


@pytest.mark.spec("scheduler::Non-matching tick is a no-op")
def test_scheduler_weekly_recalibration_non_matching_tick_noops(repository):
    calls = []
    scheduler = _recalibration_scheduler(repository, calls)

    cron_now = datetime.now(UTC).replace(hour=5, minute=1, second=0, microsecond=0)

    assert scheduler.tick_recalibration(cron_now.isoformat()) is None
    assert calls == []


@pytest.mark.spec("scheduler::Recalibration does not overlap a running job")
def test_scheduler_weekly_recalibration_noops_when_daily_lock_held(repository):
    calls = []
    lock = RunLockManager(repository).acquire("daily")
    scheduler = _recalibration_scheduler(repository, calls)

    cron_now = datetime.now(UTC).replace(hour=5, minute=0, second=0, microsecond=0)

    try:
        assert scheduler.tick_recalibration(cron_now.isoformat()) is None
    finally:
        lock.release()
    assert calls == []


@pytest.mark.spec("scheduler::Manual trigger starts a run")
@pytest.mark.spec("scheduler::Apply pipeline runs")
@pytest.mark.spec("scheduler::Urgent run after paid charge")
@pytest.mark.spec("scheduler::Urgent trigger runs out of schedule")
@pytest.mark.spec("hermes-inventory::Manual run can request full inventory")
def test_manual_and_urgent_triggers_start_pipeline_without_combo_test(repository):
    calls = []

    def runner(trigger, run_type):
        calls.append((trigger, run_type))
        return PipelineRunResult(
            run_id=f"run-{len(calls)}",
            status="success",
            exit_code=0,
            changed=False,
            stage_results=[],
            skipped_stages=[],
        )

    scheduler = Scheduler(repository, cron="0 4 * * *", pipeline_runner=runner)

    assert scheduler.trigger("manual-full").exit_code == 0
    assert scheduler.trigger("manual-provider", provider="openai").exit_code == 0
    assert scheduler.trigger("manual-role", role="coder").exit_code == 0
    assert scheduler.trigger("event-provider-added", provider="anthropic").exit_code == 0
    assert scheduler.trigger("urgent-paid-charge", provider="qiniu").exit_code == 0

    assert calls == [
        ("manual-full", "full"),
        ("manual-provider:openai", "provider"),
        ("manual-role:coder", "role"),
        ("event-provider-added:anthropic", "provider"),
        ("urgent-paid-charge:qiniu", "provider"),
    ]


@pytest.mark.spec("hermes-inventory::Unknown role event does not create inventory or combo")
def test_unknown_role_trigger_stays_role_scoped_without_full_inventory_or_combo(repository):
    calls = []
    full_inventory_requests = []
    combo_creations = []

    def runner(trigger, run_type):
        calls.append((trigger, run_type))
        if run_type == "full":
            full_inventory_requests.append(trigger)
            combo_creations.append(f"fmo-{trigger}")
        return PipelineRunResult(
            run_id="run-role",
            status="success",
            exit_code=0,
            changed=False,
            stage_results=[],
            skipped_stages=[],
        )

    scheduler = Scheduler(repository, cron="0 4 * * *", pipeline_runner=runner)

    result = scheduler.trigger("manual-role", role="unknown-role")

    assert result.exit_code == 0
    assert calls == [("manual-role:unknown-role", "role")]
    assert full_inventory_requests == []
    assert combo_creations == []
