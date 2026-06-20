from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from fmo.persistence import Repository


EXIT_CODES = {
    "success": 0,
    "partial_stale": 2,
    "validation_failed": 3,
    "not_implemented": 3,
    "external_dependency_failed": 4,
    "unsafe_to_apply": 5,
    "apply_failed_rolled_back": 6,
    "rollback_failed": 7,
}

CANONICAL_STAGE_NAMES = [
    "external-metadata-sync",
    "free-candidate-discovery",
    "model-matching",
    "quota-research",
    "access-classification",
    "probing",
    "telemetry-sync",
    "quota-sync",
    "hermes-inventory",
    "role-scoring",
    "allocation",
    "diff",
    "apply",
    "audit",
]

STOP_STATUSES = {
    "partial_stale",
    "validation_failed",
    "not_implemented",
    "external_dependency_failed",
    "unsafe_to_apply",
    "apply_failed_rolled_back",
    "rollback_failed",
}


@dataclass(frozen=True)
class StageResult:
    status: str
    idempotency_key: str | None = None
    changed: bool = False
    reason: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PipelineContext:
    run_id: str
    repository: Repository
    config: dict[str, Any]


StageCallable = Callable[[PipelineContext], StageResult]


@dataclass(frozen=True)
class Stage:
    name: str
    run: StageCallable
    idempotency_key: str | Callable[[PipelineContext], str | None] | None = None


@dataclass(frozen=True)
class PipelineRunResult:
    run_id: str
    status: str
    exit_code: int
    changed: bool
    stage_results: list[dict[str, Any]]
    skipped_stages: list[str]


class PipelineRunner:
    def __init__(
        self,
        repository: Repository,
        *,
        stages: Sequence[Stage] | None = None,
        code_version: str = "dev",
        config_hash: str = "default",
        config: dict[str, Any] | None = None,
    ):
        self.repository = repository
        self.stages = list(stages or [])
        self.code_version = code_version
        self.config_hash = config_hash
        self.config = config or {}

    def run(self, *, trigger: str, run_type: str = "full") -> PipelineRunResult:
        with self.repository.database.transaction() as transaction:
            run = self.repository.runs.create(
                transaction,
                run_type=run_type,
                trigger=trigger,
                status="running",
                code_version=self.code_version,
                config_hash=self.config_hash,
            )
        run_id = str(run["id"])
        context = PipelineContext(run_id=run_id, repository=self.repository, config=self.config)
        stage_records: list[dict[str, Any]] = []
        skipped_stages: list[str] = []
        changed = False
        status = "success"

        for stage in self.stages:
            record = self._run_stage(context, stage)
            stage_records.append(record)
            if record["skipped"]:
                skipped_stages.append(stage.name)
            changed = changed or bool(record["changed"])
            status = worse_status(status, record["status"])
            if record["status"] in STOP_STATUSES:
                break

        with self.repository.database.transaction() as transaction:
            self.repository.runs.finish(transaction, run_id, status=status, stages=stage_records)
        return PipelineRunResult(
            run_id=run_id,
            status=status,
            exit_code=outcome_exit_code(status),
            changed=changed,
            stage_results=stage_records,
            skipped_stages=skipped_stages,
        )

    def _run_stage(self, context: PipelineContext, stage: Stage) -> dict[str, Any]:
        idempotency_key = self._idempotency_key(context, stage)
        if idempotency_key and self._has_prior_success(stage.name, idempotency_key):
            skipped_result = StageResult(status="success", idempotency_key=idempotency_key)
            return _stage_record(stage.name, skipped_result, skipped=True, changed=False)
        result = stage.run(context)
        if result.idempotency_key is None and idempotency_key is not None:
            result = StageResult(
                status=result.status,
                idempotency_key=idempotency_key,
                changed=result.changed,
                reason=result.reason,
                details=result.details,
            )
        return _stage_record(stage.name, result, skipped=False, changed=result.changed)

    def _idempotency_key(self, context: PipelineContext, stage: Stage) -> str | None:
        if callable(stage.idempotency_key):
            return stage.idempotency_key(context)
        return stage.idempotency_key

    def _has_prior_success(self, stage_name: str, idempotency_key: str) -> bool:
        with self.repository.database.transaction() as transaction:
            return (
                self.repository.runs.last_successful_stage(
                    transaction,
                    stage_name=stage_name,
                    idempotency_key=idempotency_key,
                )
                is not None
            )


def outcome_exit_code(status: str) -> int:
    try:
        return EXIT_CODES[status]
    except KeyError as exc:
        raise ValueError(f"unknown pipeline status: {status}") from exc


def worse_status(left: str, right: str) -> str:
    return right if outcome_exit_code(right) >= outcome_exit_code(left) else left


def _stage_record(stage_name: str, result: StageResult, *, skipped: bool, changed: bool) -> dict[str, Any]:
    return {
        "name": stage_name,
        "status": result.status,
        "idempotency_key": result.idempotency_key,
        "skipped": skipped,
        "changed": changed,
        "reason": result.reason,
        "details": result.details,
    }
