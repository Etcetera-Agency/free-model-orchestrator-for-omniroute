from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from fmo.config import StartupConfig
from fmo.external_metadata import ExternalMetadataError
from fmo.metadata_sync import sync_external_metadata
from fmo.omniroute import OmniRouteClient
from fmo.persistence import Database, Repository
from fmo.pipeline import CANONICAL_STAGE_NAMES, PipelineContext, PipelineRunner, PipelineRunResult, Stage, StageResult


@dataclass(frozen=True)
class RuntimeCliResult:
    exit_code: int
    changed: bool
    combo_test_called: bool = False
    error_reason: str | None = None
    output: str | None = None


@dataclass(frozen=True)
class ComposedRuntime:
    repository: Repository
    omniroute_client: OmniRouteClient
    stages: Sequence[Stage]

    def run_command(self, command: str, args: argparse.Namespace) -> RuntimeCliResult:
        selected_stages = stages_for_command(command, self.stages)
        result = PipelineRunner(
            self.repository,
            stages=selected_stages,
            config={"command": command, "dry_run": getattr(args, "dry_run", False)},
        ).run(trigger=command, run_type=_run_type(command))
        return _cli_result(result)

    def read_diagnostics(self, kind: str, identifier: str) -> str:
        with self.repository.database.transaction() as transaction:
            if kind == "endpoint":
                row = self.repository.provider_endpoints.get(transaction, identifier)
            else:
                row = _latest_role_diagnostic(transaction, identifier)
        if row is None:
            return f"{kind}:{identifier}:not_found"
        return f"{kind}:{identifier}:{row}"


MetadataSync = Callable[..., object]


def compose_runtime(
    config: StartupConfig,
    *,
    metadata_sync: MetadataSync | None = None,
) -> ComposedRuntime:
    if config.database_url is None:
        raise ValueError("database_url_required")
    repository = Repository(Database(config.database_url))
    client = OmniRouteClient(base_url=config.omniroute_url)
    return ComposedRuntime(
        repository=repository,
        omniroute_client=client,
        stages=build_canonical_stages(metadata_sync=metadata_sync),
    )


def build_canonical_stages(*, metadata_sync: MetadataSync | None = None) -> list[Stage]:
    sync = metadata_sync or sync_external_metadata
    stage_by_name = {
        "external-metadata-sync": Stage("external-metadata-sync", _metadata_stage(sync)),
        "free-candidate-discovery": Stage("free-candidate-discovery", _successful_stage("free-candidate-discovery")),
        "model-matching": Stage("model-matching", _successful_stage("model-matching")),
        "quota-research": Stage("quota-research", _successful_stage("quota-research")),
        "access-classification": Stage("access-classification", _successful_stage("access-classification")),
        "probing": Stage("probing", _successful_stage("probing")),
        "telemetry-sync": Stage("telemetry-sync", _successful_stage("telemetry-sync")),
        "quota-sync": Stage("quota-sync", _successful_stage("quota-sync")),
        "role-scoring": Stage("role-scoring", _successful_stage("role-scoring")),
        "allocation": Stage("allocation", _successful_stage("allocation")),
        "diff": Stage("diff", _successful_stage("diff")),
        "apply": Stage("apply", _successful_stage("apply")),
        "audit": Stage("audit", _successful_stage("audit")),
    }
    return [stage_by_name[name] for name in CANONICAL_STAGE_NAMES]


def stages_for_command(command: str, stages: Sequence[Stage]) -> list[Stage]:
    stage_by_name = {stage.name: stage for stage in stages}
    if command == "full":
        return list(stages)
    stage_name = _COMMAND_STAGE_NAMES[command]
    return [stage_by_name[stage_name]]


def _metadata_stage(sync: MetadataSync) -> Callable[[PipelineContext], StageResult]:
    def run(context: PipelineContext) -> StageResult:
        try:
            result = sync(dry_run=bool(context.config.get("dry_run", False)))
        except ExternalMetadataError as exc:
            return StageResult(status="external_dependency_failed", reason=exc.reason)
        except Exception as exc:
            return StageResult(status="external_dependency_failed", reason=str(exc))
        if not bool(context.config.get("dry_run", False)):
            with context.repository.database.transaction() as transaction:
                context.repository.external_metadata.store_sync_result(
                    transaction,
                    candidates=result.candidates,
                    aa_snapshot=result.aa_snapshot,
                    run_id=context.run_id,
                )
        return StageResult(status="success", changed=not bool(context.config.get("dry_run", False)))

    return run


def _successful_stage(name: str) -> Callable[[PipelineContext], StageResult]:
    def run(_context: PipelineContext) -> StageResult:
        return StageResult(status="success", idempotency_key=f"{name}:default")

    return run


def _latest_role_diagnostic(transaction: Any, role_id: str) -> dict[str, Any] | None:
    row = transaction.execute(
        """
        SELECT r.id AS role_id, ap.status, ap.targets, ap.constraint_report
        FROM roles r
        LEFT JOIN allocation_plans ap ON ap.role_id = r.id
        WHERE r.id = %(role_id)s
        ORDER BY ap.created_at DESC NULLS LAST
        LIMIT 1
        """,
        {"role_id": role_id},
    ).fetchone()
    return dict(row) if row is not None else None


def _cli_result(result: PipelineRunResult) -> RuntimeCliResult:
    failing_stage = next((stage for stage in result.stage_results if stage["status"] != "success"), None)
    return RuntimeCliResult(
        exit_code=result.exit_code,
        changed=result.changed,
        combo_test_called=False,
        error_reason=failing_stage.get("reason") if failing_stage else None,
    )


def _run_type(command: str) -> str:
    if command == "full":
        return "full"
    return _COMMAND_STAGE_NAMES[command]


_COMMAND_STAGE_NAMES = {
    "sync-free-registry": "external-metadata-sync",
    "discover-accounts": "free-candidate-discovery",
    "scan-providers": "free-candidate-discovery",
    "research-quotas": "quota-research",
    "classify-access": "access-classification",
    "sync-metadata": "external-metadata-sync",
    "match-models": "model-matching",
    "probe-models": "probing",
    "sync-telemetry": "telemetry-sync",
    "sync-quotas": "quota-sync",
    "score-roles": "role-scoring",
    "allocate": "allocation",
    "diff": "diff",
    "apply": "apply",
    "rollback": "audit",
}
