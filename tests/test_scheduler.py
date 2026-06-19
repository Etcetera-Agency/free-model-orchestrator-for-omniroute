from pathlib import Path

import pytest

from fmo.db import MigrationRunner
from fmo.persistence import Database, Repository
from fmo.pipeline import PipelineRunResult
from fmo.scheduler import RunLockManager, Scheduler


@pytest.fixture()
def repository(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    return Repository(Database(postgres_url))


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

    result = scheduler.tick("2026-06-18T04:00:00Z")

    assert result.exit_code == 0
    assert calls == [("scheduled", "full")]


@pytest.mark.spec("scheduler::Manual trigger starts a run")
@pytest.mark.spec("scheduler::Apply pipeline runs")
@pytest.mark.spec("scheduler::Urgent run after paid charge")
@pytest.mark.spec("scheduler::Urgent trigger runs out of schedule")
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
