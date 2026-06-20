from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from fmo.persistence import Repository
from fmo.pipeline import PipelineRunResult


PipelineInvoker = Callable[[str, str], PipelineRunResult]


@dataclass(frozen=True)
class RunLock:
    manager: "RunLockManager"
    name: str
    token: str | None
    acquired: bool

    def release(self) -> None:
        if self.token:
            self.manager.release(self.token)


class RunLockManager:
    def __init__(self, repository: Repository):
        self.repository = repository

    def acquire(self, name: str, *, scope: str | None = None) -> RunLock:
        lock_name = _lock_name(name, scope)
        with self.repository.database.transaction() as transaction:
            token = self.repository.locks.acquire(transaction, lock_name)
        return RunLock(self, lock_name, token, token is not None)

    @contextmanager
    def hold(self, name: str, *, scope: str | None = None) -> Iterator[RunLock]:
        lock = self.acquire(name, scope=scope)
        try:
            yield lock
        finally:
            lock.release()

    def release(self, token: str) -> None:
        with self.repository.database.transaction() as transaction:
            self.repository.locks.release(transaction, token)


class Scheduler:
    def __init__(self, repository: Repository, *, cron: str, pipeline_runner: PipelineInvoker):
        self.repository = repository
        self.cron = cron
        self.pipeline_runner = pipeline_runner
        self.locks = RunLockManager(repository)

    def tick(self, timestamp: str) -> PipelineRunResult | None:
        if not _cron_matches(self.cron, timestamp):
            return None
        return self.trigger("scheduled")

    def trigger(self, trigger: str, *, provider: str | None = None, role: str | None = None) -> PipelineRunResult:
        run_type, lock_scope, pipeline_trigger = _trigger_plan(trigger, provider=provider, role=role)
        with self.locks.hold("daily" if run_type == "full" else "provider-scan", scope=lock_scope) as lock:
            if not lock.acquired:
                return PipelineRunResult(
                    run_id="",
                    status="partial_stale",
                    exit_code=2,
                    changed=False,
                    stage_results=[],
                    skipped_stages=[],
                )
            return self.pipeline_runner(pipeline_trigger, run_type)


def _lock_name(name: str, scope: str | None) -> str:
    return f"{name}:{scope}" if scope else name


def _cron_matches(cron: str, timestamp: str) -> bool:
    minute, hour, *_rest = cron.split(" ")
    time_part = timestamp.split("T", 1)[1]
    current_hour, current_minute, *_seconds = time_part.split(":")
    return int(minute) == int(current_minute) and int(hour) == int(current_hour)


def _trigger_plan(trigger: str, *, provider: str | None, role: str | None) -> tuple[str, str | None, str]:
    if trigger == "manual-provider":
        return "provider", provider, f"manual-provider:{provider}"
    if trigger == "manual-role":
        return "role", role, f"manual-role:{role}"
    if trigger == "event-provider-added":
        return "provider", provider, f"event-provider-added:{provider}"
    if trigger == "urgent-paid-charge":
        return "provider", provider, f"urgent-paid-charge:{provider}"
    return "full", None, trigger
