from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from urllib.parse import urljoin

from fmo.aa_index_runtime import _run_aa_index_command, select_llm_model
from fmo.combo_reader import read_current_combos
from fmo.composition_contracts import RuntimeCliResult
from fmo.composition_stages import (
    MetadataSync,
    StageAdapters,
    StageDependencies,
    _account_discovery_stage,
    _adapter_stage,
    _default_live_catalog_refresh,
    _effect_result,
    _free_candidate_stage,
    _latest_role_diagnostic,
    _metadata_stage,
)
from fmo.config import StartupConfig
from fmo.llm_runtime import LlmProviderConfig, SharedInstructorRuntime, build_instructor_runtime
from fmo.metadata_sync import sync_external_metadata
from fmo.omniroute import OmniRouteClient, OmniRouteVersionGate
from fmo.persistence import Database, Repository
from fmo.pipeline import CANONICAL_STAGE_NAMES, PipelineContext, PipelineRunner, PipelineRunResult, Stage, StageResult
from fmo.pool_publisher import compose_pool_generation, publish_pool_generation, usage_feedback
from fmo.profile_normalization import ProfileNormalizationResult
from fmo.profile_normalization import normalize_profiles as normalize_profile_configs
from fmo.provider_sweep import ProviderSweepResult, sweep_provider_models
from fmo.scheduler import Scheduler


@dataclass(frozen=True)
class ComposedRuntime:
    repository: Repository
    omniroute_client: OmniRouteClient
    stages: Sequence[Stage]
    cron: str
    llm_runtime: SharedInstructorRuntime
    config: StartupConfig
    live_catalog_refresh: Callable[[Repository, OmniRouteClient, str], object]

    def run_command(self, command: str, args: argparse.Namespace) -> RuntimeCliResult:
        refresh_result = self._refresh_live_catalog()
        if refresh_result is not None:
            return refresh_result
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
        refresh_result = self._refresh_live_catalog()
        if refresh_result is not None:
            return f"{kind}:{identifier}:live_catalog_refresh_failed:{refresh_result.error_reason}"
        with self.repository.database.transaction() as transaction:
            if kind == "endpoint":
                row = self.repository.provider_endpoints.get(transaction, identifier)
                rejection = _latest_endpoint_rejection(transaction, identifier)
            else:
                row = _latest_role_diagnostic(transaction, identifier)
                rejection = None
        if row is None:
            return f"{kind}:{identifier}:not_found"
        if rejection:
            return f"{kind}:{identifier}:{row}:rejection={rejection}"
        return f"{kind}:{identifier}:{row}"

    def run_scheduler_once(self, timestamp: str) -> RuntimeCliResult:
        scheduler = Scheduler(self.repository, cron=self.cron, pipeline_runner=self.run_pipeline)
        result = scheduler.tick(timestamp)
        if result is None:
            return RuntimeCliResult(exit_code=0, changed=False)
        return _cli_result(result)

    def run_pipeline(self, trigger: str, run_type: str) -> PipelineRunResult:
        stages = [
            Stage("live-catalog-refresh", self._live_catalog_refresh_stage),
            *list(self.stages),
        ]
        return PipelineRunner(
            self.repository,
            stages=stages,
            config={"command": run_type, "dry_run": False},
        ).run(trigger=trigger, run_type=run_type)

    def run_aa_index(self, command: str, _args: argparse.Namespace) -> RuntimeCliResult:
        return _run_aa_index_command(self.repository, self.llm_runtime, self.config, command)

    def normalize_profiles(self, args: argparse.Namespace) -> RuntimeCliResult:
        refresh_result = self._refresh_live_catalog()
        if refresh_result is not None:
            return refresh_result
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

    def sweep_provider_models(self, args: argparse.Namespace) -> ProviderSweepResult:
        def log(message: str) -> None:
            print(message, flush=True)

        return sweep_provider_models(
            self.repository,
            self.omniroute_client,
            provider=args.provider,
            limit=args.limit,
            offset=args.offset,
            force=args.force,
            dry_run=args.dry_run,
            delay_seconds=args.delay_seconds,
            timeout_seconds=args.timeout_seconds,
            omniroute_instance_id=self.config.omniroute_url,
            log=log,
        )

    def _refresh_live_catalog(self) -> RuntimeCliResult | None:
        try:
            self.live_catalog_refresh(self.repository, self.omniroute_client, self.config.omniroute_url)
        except Exception as exc:
            return RuntimeCliResult(exit_code=4, changed=False, error_reason=f"live_catalog_refresh:{exc}")
        return None

    def _live_catalog_refresh_stage(self, _context: PipelineContext):
        try:
            self.live_catalog_refresh(self.repository, self.omniroute_client, self.config.omniroute_url)
        except Exception as exc:
            return StageResult(status="external_dependency_failed", reason=f"live_catalog_refresh:{exc}")
        return _effect_result("live-catalog-refresh", changed=True)


def compose_runtime(
    config: StartupConfig,
    *,
    metadata_sync: MetadataSync | None = None,
    adapters: StageAdapters | None = None,
) -> ComposedRuntime:
    if config.database_url is None:
        raise ValueError("database_url_required")
    if config.omniroute_api_key is None:
        raise ValueError("omniroute_api_key_required")
    selected_adapters = adapters or StageAdapters(live_catalog_refresh=_default_live_catalog_refresh())
    repository = Repository(Database(config.database_url))
    client = OmniRouteClient(base_url=config.omniroute_url, api_key=config.omniroute_api_key)
    llm_runtime = build_production_llm_runtime(config, repository, live_quota_client=client, adapters=selected_adapters)
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
        stages=build_canonical_stages(
            dependencies=dependencies, metadata_sync=metadata_sync, adapters=selected_adapters
        ),
        cron=config.hermes_inventory_cron,
        llm_runtime=llm_runtime,
        config=config,
        live_catalog_refresh=selected_adapters.live_catalog_refresh,
    )


def build_production_llm_runtime(
    config: StartupConfig,
    repository: Repository,
    *,
    live_quota_client=None,
    adapters: StageAdapters | None = None,
) -> SharedInstructorRuntime:
    selected_adapters = adapters or StageAdapters()
    provider = LlmProviderConfig(
        base_url=urljoin(config.omniroute_url.rstrip("/") + "/", "v1"),
        api_key=config.omniroute_api_key or "",
    )
    return build_instructor_runtime(
        provider=provider,
        model_resolver=lambda: select_llm_model(repository, config, live_quota_client),
        instructor_from_openai=selected_adapters.instructor_from_openai,
        openai_client_factory=selected_adapters.openai_client_factory,
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
    if deps.hermes_inventory_adapter is None and stage_adapters.hermes_inventory is not None:
        deps = StageDependencies(
            repository=deps.repository,
            omniroute_client=deps.omniroute_client,
            config=deps.config,
            llm_runtime=deps.llm_runtime,
            hermes_inventory_adapter=stage_adapters.hermes_inventory,
        )
    stage_by_name = {
        "external-metadata-sync": Stage("external-metadata-sync", _metadata_stage(sync)),
        "free-candidate-discovery": Stage("free-candidate-discovery", _free_candidate_stage(deps, stage_adapters)),
        "account-discovery": Stage("account-discovery", _account_discovery_stage(deps, stage_adapters)),
        "model-matching": Stage("model-matching", _adapter_stage("model-matching", deps, stage_adapters)),
        "access-classification": Stage(
            "access-classification", _adapter_stage("access-classification", deps, stage_adapters)
        ),
        "probing": Stage("probing", _adapter_stage("probing", deps, stage_adapters)),
        "telemetry-sync": Stage("telemetry-sync", _adapter_stage("telemetry-sync", deps, stage_adapters)),
        "hermes-inventory": Stage("hermes-inventory", _adapter_stage("hermes-inventory", deps, stage_adapters)),
        "role-lifecycle": Stage("role-lifecycle", _adapter_stage("role-lifecycle", deps, stage_adapters)),
        "role-scoring": Stage("role-scoring", _adapter_stage("role-scoring", deps, stage_adapters)),
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
    version_gate = OmniRouteVersionGate(known_contract_versions or {"1.4.0"})
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


def _latest_endpoint_rejection(transaction, endpoint_id: str) -> str | None:
    row = transaction.execute(
        """
        SELECT rejection_reasons
        FROM role_scores
        WHERE endpoint_id = %(endpoint_id)s
          AND eligibility = false
          AND rejection_reasons IS NOT NULL
        ORDER BY calculated_at DESC
        LIMIT 1
        """,
        {"endpoint_id": endpoint_id},
    ).fetchone()
    if row is None:
        return None
    reasons = row["rejection_reasons"] or []
    return ",".join(str(reason) for reason in reasons)


def _run_type(command: str) -> str:
    if command == "full":
        return "full"
    return _COMMAND_STAGE_NAMES[command]


_COMMAND_STAGE_NAMES = {
    "sync-free-registry": "free-candidate-discovery",
    "discover-accounts": "account-discovery",
    "scan-providers": "free-candidate-discovery",
    "classify-access": "access-classification",
    "sync-metadata": "external-metadata-sync",
    "match-models": "model-matching",
    "probe-models": "probing",
    "sync-telemetry": "telemetry-sync",
    "sync-hermes-inventory": "hermes-inventory",
    "reconcile-roles": "role-lifecycle",
    "score-roles": "role-scoring",
    "forecast-demand": "demand-forecast",
}
