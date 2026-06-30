from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import dataclass

from fmo.combo_reader import read_current_combos
from fmo.composition_contracts import RuntimeCliResult
from fmo.composition_stages import (
    StageAdapters,
    StageDependencies,
    _adapter_stage,
    _latest_role_diagnostic,
)
from fmo.config import StartupConfig
from fmo.llm_runtime import SharedInstructorRuntime
from fmo.omniroute import OmniRouteClient, OmniRouteVersionGate
from fmo.persistence import Database, Repository
from fmo.pipeline import CANONICAL_STAGE_NAMES, PipelineContext, PipelineRunner, PipelineRunResult, Stage, StageResult
from fmo.pool_publisher import compose_pool_generation, publish_pool_generation, usage_feedback
from fmo.profile_normalization import ProfileNormalizationResult
from fmo.profile_normalization import normalize_profiles as normalize_profile_configs
from fmo.scheduler import Scheduler


@dataclass(frozen=True)
class ComposedRuntime:
    repository: Repository
    omniroute_client: OmniRouteClient
    stages: Sequence[Stage]
    cron: str
    llm_runtime: SharedInstructorRuntime
    config: StartupConfig

    def run_command(self, command: str, args: argparse.Namespace) -> RuntimeCliResult:
        selected_stages = stages_for_command(command, self.stages)
        result = PipelineRunner(
            self.repository,
            stages=selected_stages,
            config={
                "command": command,
                "dry_run": getattr(args, "dry_run", False),
                "run_id": getattr(args, "run_id", None),
                "endpoint": getattr(args, "endpoint", None),
                "provider": getattr(args, "provider", None),
                "account": getattr(args, "account", None),
                "role": getattr(args, "role", None),
            },
        ).run(trigger=command, run_type=_run_type(command))
        return _cli_result(result)

    def read_diagnostics(self, kind: str, identifier: str) -> str:
        with self.repository.database.transaction() as transaction:
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

    def normalize_profiles(self, args: argparse.Namespace) -> RuntimeCliResult:
        if not self.config.hermes_home:
            return RuntimeCliResult(exit_code=3, changed=False, error_reason="hermes_home_required")
        # AICODE-NOTE: profile normalization never creates combos; live combos
        # are only lookup targets for raw/missing Hermes slots.
        result = normalize_profile_configs(
            self.config.hermes_home,
            current_combos=read_current_combos(self.omniroute_client),
            dry_run=getattr(args, "dry_run", False),
        )
        return RuntimeCliResult(
            exit_code=result.exit_code,
            changed=result.changed,
            output=_profile_normalization_output(result),
        )


def compose_runtime(
    config: StartupConfig,
    *,
    adapters: StageAdapters | None = None,
) -> ComposedRuntime:
    if config.database_url is None:
        raise ValueError("database_url_required")
    if config.omniroute_api_key is None:
        raise ValueError("omniroute_api_key_required")
    selected_adapters = adapters or StageAdapters()
    repository = Repository(Database(config.database_url))
    client = OmniRouteClient(base_url=config.omniroute_url, api_key=config.omniroute_api_key)
    llm_runtime = build_production_llm_runtime()
    dependencies = StageDependencies(
        repository=repository,
        omniroute_client=client,
        config=config,
        llm_runtime=llm_runtime,
        hermes_inventory_adapter=selected_adapters.hermes_inventory,
    )
    return ComposedRuntime(
        repository=repository,
        omniroute_client=client,
        stages=build_publisher_stages(dependencies=dependencies),
        cron=config.hermes_inventory_cron,
        llm_runtime=llm_runtime,
        config=config,
    )


def build_production_llm_runtime() -> SharedInstructorRuntime | None:
    return None


def build_canonical_stages(
    *,
    dependencies: StageDependencies | None = None,
    adapters: StageAdapters | None = None,
) -> list[Stage]:
    deps = dependencies or StageDependencies(repository=None, omniroute_client=None)
    stage_adapters = adapters or StageAdapters()
    if deps.hermes_inventory_adapter is None and stage_adapters.hermes_inventory is not None:
        deps = StageDependencies(
            repository=deps.repository,
            omniroute_client=deps.omniroute_client,
            config=deps.config,
            llm_runtime=deps.llm_runtime,
            hermes_inventory_adapter=stage_adapters.hermes_inventory,
        )
    stage_by_name = {
        "hermes-inventory": Stage("hermes-inventory", _adapter_stage("hermes-inventory", deps, stage_adapters)),
        "role-lifecycle": Stage("role-lifecycle", _adapter_stage("role-lifecycle", deps, stage_adapters)),
        "demand-forecast": Stage("demand-forecast", _adapter_stage("demand-forecast", deps, stage_adapters)),
        "audit": Stage("audit", _adapter_stage("audit", deps, stage_adapters)),
    }
    return [stage_by_name[name] for name in CANONICAL_STAGE_NAMES]


def build_publisher_stages(
    *,
    dependencies: StageDependencies,
    known_contract_versions: set[str] | None = None,
) -> list[Stage]:
    stage_adapters = StageAdapters()
    version_gate = OmniRouteVersionGate(known_contract_versions or {">=3.7.0"})
    return [
        Stage("hermes-inventory", _adapter_stage("hermes-inventory", dependencies, stage_adapters)),
        Stage("role-lifecycle", _adapter_stage("role-lifecycle", dependencies, stage_adapters)),
        Stage("demand-forecast", _adapter_stage("demand-forecast", dependencies, stage_adapters)),
        Stage("compose", _compose_pool_stage),
        Stage(
            "publish",
            lambda context: _publish_pool_stage(context, dependencies=dependencies, version_gate=version_gate),
        ),
        Stage("usage-feedback", lambda context: _usage_feedback_stage(context, dependencies=dependencies)),
    ]


def _compose_pool_stage(context: PipelineContext) -> StageResult:
    try:
        generation = _compose_pool_generation_from_repository(context)
    except ValueError as exc:
        return StageResult(status="validation_failed", reason=str(exc), details={"effect": "idempotent_no_change"})
    context.config["pool_generation"] = generation
    return StageResult(
        status="success",
        changed=True,
        details={"effect": "repository_write", "pool_count": len(generation["pools"])},
    )


def _publish_pool_stage(
    context: PipelineContext,
    *,
    dependencies: StageDependencies,
    version_gate: OmniRouteVersionGate,
) -> StageResult:
    if dependencies.omniroute_client is None:
        return StageResult(
            status="external_dependency_failed",
            reason="omniroute_client_required",
            details={"effect": "idempotent_no_change"},
        )
    generation = context.config.get("pool_generation")
    if not isinstance(generation, dict):
        return StageResult(
            status="validation_failed",
            reason="pool_generation_required",
            details={"effect": "idempotent_no_change"},
        )
    try:
        result = publish_pool_generation(
            context.repository,
            dependencies.omniroute_client,
            generation,
            run_id=context.run_id,
            version_gate=version_gate,
        )
    except Exception as exc:
        return StageResult(
            status="external_dependency_failed",
            reason=f"pool_publish:{exc}",
            details={"effect": "idempotent_no_change"},
        )
    return StageResult(
        status="success",
        idempotency_key=result.payload_hash,
        changed=True,
        details={"effect": "omniroute_call", "payload_hash": result.payload_hash, "status": result.status},
    )


def _usage_feedback_stage(context: PipelineContext, *, dependencies: StageDependencies) -> StageResult:
    if dependencies.omniroute_client is None:
        return StageResult(
            status="external_dependency_failed",
            reason="omniroute_client_required",
            details={"effect": "idempotent_no_change"},
        )
    try:
        feedback = usage_feedback(dependencies.omniroute_client)
    except Exception as exc:
        return StageResult(
            status="external_dependency_failed",
            reason=f"usage_feedback:{exc}",
            details={"effect": "idempotent_no_change"},
        )
    context.config["usage_feedback"] = feedback
    return StageResult(
        status="success",
        changed=bool(feedback),
        details={"effect": "omniroute_call", "pool_count": len(feedback.get("pools", []))},
    )


def _compose_pool_generation_from_repository(context: PipelineContext) -> dict:
    with context.repository.database.transaction() as transaction:
        roles = [
            dict(row)
            for row in transaction.execute(
                """
                SELECT r.id, r.requirements, r.role_lifecycle_status,
                       r.minimum_quality_metric, r.minimum_quality_value,
                       r.maximum_quality_metric, r.maximum_quality_value,
                       COALESCE(consumers.consumer_count, 0) AS consumer_count
                FROM roles r
                LEFT JOIN (
                  SELECT role_id, count(*) AS consumer_count
                  FROM role_consumers
                  WHERE active = true
                  GROUP BY role_id
                ) consumers ON consumers.role_id = r.id
                ORDER BY r.id
                """
            ).fetchall()
        ]
        demand = {
            row["role_id"]: float(row["protected_requests"])
            for row in transaction.execute(
                """
                SELECT DISTINCT ON (role_id) role_id, protected_requests
                FROM role_demand_forecasts
                ORDER BY role_id, created_at DESC
                """
            ).fetchall()
        }
    return compose_pool_generation(roles, demand, generation=context.config.get("generation"))


def stages_for_command(command: str, stages: Sequence[Stage]) -> list[Stage]:
    stage_by_name = {stage.name: stage for stage in stages}
    if command == "full":
        return list(stages)
    stage_name = _COMMAND_STAGE_NAMES[command]
    return [stage_by_name[stage_name]]


def _cli_result(result: PipelineRunResult) -> RuntimeCliResult:
    failing_stage = next((stage for stage in result.stage_results if stage["status"] != "success"), None)
    return RuntimeCliResult(
        exit_code=result.exit_code,
        changed=result.changed,
        combo_test_called=any(bool(stage["details"].get("combo_test_called")) for stage in result.stage_results),
        error_reason=failing_stage.get("reason") if failing_stage else None,
    )


def _profile_normalization_output(result: ProfileNormalizationResult) -> str:
    lines = [f"{rewrite.config_path}:{rewrite.slot}:{rewrite.old}->{rewrite.new}" for rewrite in result.rewrites]
    return "\n".join(lines)


def _run_type(command: str) -> str:
    if command == "full":
        return "full"
    return _COMMAND_STAGE_NAMES[command]


_COMMAND_STAGE_NAMES = {
    "sync-hermes-inventory": "hermes-inventory",
    "reconcile-roles": "role-lifecycle",
    "forecast-demand": "demand-forecast",
}
