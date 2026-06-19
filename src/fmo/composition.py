from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from fmo.config import StartupConfig
from fmo.external_metadata import ExternalMetadataError
from fmo.metadata_sync import sync_external_metadata
from fmo.omniroute import OmniRouteClient
from fmo.persistence import Database, Repository
from fmo.pipeline import CANONICAL_STAGE_NAMES, PipelineContext, PipelineRunner, PipelineRunResult, Stage, StageResult
from fmo.registry import RegistryFetchError, persist_free_registry_outcome, sync_live_free_registry
from fmo.scanner import CatalogFetchError, CatalogScanner, scan_live_omniroute_catalogs
from fmo.scheduler import Scheduler


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
    cron: str

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

    def run_scheduler_once(self, timestamp: str) -> RuntimeCliResult:
        scheduler = Scheduler(self.repository, cron=self.cron, pipeline_runner=self.run_pipeline)
        result = scheduler.tick(timestamp)
        if result is None:
            return RuntimeCliResult(exit_code=0, changed=False)
        return _cli_result(result)

    def run_pipeline(self, trigger: str, run_type: str) -> PipelineRunResult:
        return PipelineRunner(
            self.repository,
            stages=list(self.stages),
            config={"command": run_type, "dry_run": False},
        ).run(trigger=trigger, run_type=run_type)


MetadataSync = Callable[..., object]
RegistrySync = Callable[[Any], object]
CatalogScan = Callable[[CatalogScanner, Any, str], object]
DomainStage = Callable[[str, "StageDependencies", PipelineContext], StageResult]


@dataclass(frozen=True)
class StageDependencies:
    repository: Repository | None
    omniroute_client: OmniRouteClient | None
    config: StartupConfig | None = None


@dataclass(frozen=True)
class StageAdapters:
    registry_sync: RegistrySync = sync_live_free_registry
    catalog_scan: CatalogScan = field(default_factory=lambda: _scan_catalogs)
    domain_stage: DomainStage = field(default_factory=lambda: _domain_stage_adapter)


def compose_runtime(
    config: StartupConfig,
    *,
    metadata_sync: MetadataSync | None = None,
    adapters: StageAdapters | None = None,
) -> ComposedRuntime:
    if config.database_url is None:
        raise ValueError("database_url_required")
    repository = Repository(Database(config.database_url))
    client = OmniRouteClient(base_url=config.omniroute_url)
    dependencies = StageDependencies(repository=repository, omniroute_client=client, config=config)
    return ComposedRuntime(
        repository=repository,
        omniroute_client=client,
        stages=build_canonical_stages(dependencies=dependencies, metadata_sync=metadata_sync, adapters=adapters),
        cron=config.hermes_inventory_cron,
    )


def build_canonical_stages(
    *,
    dependencies: StageDependencies | None = None,
    metadata_sync: MetadataSync | None = None,
    adapters: StageAdapters | None = None,
) -> list[Stage]:
    sync = metadata_sync or sync_external_metadata
    deps = dependencies or StageDependencies(repository=None, omniroute_client=None)
    stage_adapters = adapters or StageAdapters()
    stage_by_name = {
        "external-metadata-sync": Stage("external-metadata-sync", _metadata_stage(sync)),
        "free-candidate-discovery": Stage("free-candidate-discovery", _free_candidate_stage(deps, stage_adapters)),
        "model-matching": Stage("model-matching", _adapter_stage("model-matching", deps, stage_adapters)),
        "quota-research": Stage("quota-research", _adapter_stage("quota-research", deps, stage_adapters)),
        "access-classification": Stage("access-classification", _adapter_stage("access-classification", deps, stage_adapters)),
        "probing": Stage("probing", _adapter_stage("probing", deps, stage_adapters)),
        "telemetry-sync": Stage("telemetry-sync", _adapter_stage("telemetry-sync", deps, stage_adapters)),
        "quota-sync": Stage("quota-sync", _adapter_stage("quota-sync", deps, stage_adapters)),
        "role-scoring": Stage("role-scoring", _adapter_stage("role-scoring", deps, stage_adapters)),
        "allocation": Stage("allocation", _adapter_stage("allocation", deps, stage_adapters)),
        "diff": Stage("diff", _adapter_stage("diff", deps, stage_adapters)),
        "apply": Stage("apply", _adapter_stage("apply", deps, stage_adapters)),
        "audit": Stage("audit", _adapter_stage("audit", deps, stage_adapters)),
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


def _free_candidate_stage(dependencies: StageDependencies, adapters: StageAdapters) -> Callable[[PipelineContext], StageResult]:
    def run(context: PipelineContext) -> StageResult:
        command = str(context.config.get("command") or "full")
        try:
            if command in {"sync-free-registry", "full"}:
                outcome = adapters.registry_sync(dependencies.omniroute_client)
                persist_free_registry_outcome(context.repository, outcome)
            if command in {"scan-providers", "discover-accounts", "full"}:
                scanner = CatalogScanner(context.repository)
                adapters.catalog_scan(scanner, dependencies.omniroute_client, _omniroute_instance_id(dependencies))
        except RegistryFetchError as exc:
            return StageResult(status="external_dependency_failed", reason=exc.reason)
        except CatalogFetchError as exc:
            return StageResult(status="external_dependency_failed", reason=exc.reason)
        except Exception as exc:
            return StageResult(status="external_dependency_failed", reason=str(exc))
        return StageResult(
            status="success",
            changed=command in {"sync-free-registry", "scan-providers", "discover-accounts", "full"},
            idempotency_key=f"free-candidate-discovery:{command}",
            details={"adapter": "free-candidate-discovery", "command": command},
        )

    return run


def _adapter_stage(
    name: str,
    dependencies: StageDependencies,
    adapters: StageAdapters,
) -> Callable[[PipelineContext], StageResult]:
    def run(context: PipelineContext) -> StageResult:
        return adapters.domain_stage(name, dependencies, context)

    return run


def _domain_stage_adapter(name: str, _dependencies: StageDependencies, _context: PipelineContext) -> StageResult:
    return StageResult(status="success", idempotency_key=f"{name}:domain-adapter", details={"adapter": name})


def _scan_catalogs(scanner: CatalogScanner, client: Any, omniroute_instance_id: str) -> object:
    return scan_live_omniroute_catalogs(scanner, client, omniroute_instance_id=omniroute_instance_id)


def _omniroute_instance_id(dependencies: StageDependencies) -> str:
    if dependencies.config is None:
        return "default"
    return dependencies.config.omniroute_url


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
    "sync-free-registry": "free-candidate-discovery",
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
