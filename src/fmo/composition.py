from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import dataclass
from urllib.parse import urljoin

from fmo.aa_index_runtime import _run_aa_index_command, select_llm_model
from fmo.composition_contracts import RuntimeCliResult
from fmo.composition_stages import (
    MetadataSync,
    StageAdapters,
    StageDependencies,
    _account_discovery_stage,
    _adapter_stage,
    _free_candidate_stage,
    _latest_role_diagnostic,
    _metadata_stage,
    _read_current_combos,
    _rollback_stage,
)
from fmo.config import StartupConfig
from fmo.llm_runtime import LlmProviderConfig, SharedInstructorRuntime, build_instructor_runtime
from fmo.metadata_sync import sync_external_metadata
from fmo.omniroute import OmniRouteClient
from fmo.persistence import Database, Repository
from fmo.pipeline import CANONICAL_STAGE_NAMES, PipelineRunner, PipelineRunResult, Stage
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

    def run_command(self, command: str, args: argparse.Namespace) -> RuntimeCliResult:
        if command == "rollback":
            selected_stages = [
                Stage(
                    "rollback",
                    lambda context: _rollback_stage(
                        StageDependencies(repository=self.repository, omniroute_client=self.omniroute_client),
                        context,
                    ),
                )
            ]
        else:
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
        return PipelineRunner(
            self.repository,
            stages=list(self.stages),
            config={"command": run_type, "dry_run": False},
        ).run(trigger=trigger, run_type=run_type)

    def run_aa_index(self, command: str, _args: argparse.Namespace) -> RuntimeCliResult:
        return _run_aa_index_command(self.repository, self.llm_runtime, self.config, command)

    def normalize_profiles(self, args: argparse.Namespace) -> RuntimeCliResult:
        if not self.config.hermes_home:
            return RuntimeCliResult(exit_code=3, changed=False, error_reason="hermes_home_required")
        # AICODE-NOTE: profile normalization never creates combos; live combos
        # are only lookup targets for raw/missing Hermes slots.
        result = normalize_profile_configs(
            self.config.hermes_home,
            current_combos=_read_current_combos(self.omniroute_client),
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
            log=log,
        )


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
    selected_adapters = adapters or StageAdapters()
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
        "quota-research": Stage("quota-research", _adapter_stage("quota-research", deps, stage_adapters)),
        "access-classification": Stage(
            "access-classification", _adapter_stage("access-classification", deps, stage_adapters)
        ),
        "probing": Stage("probing", _adapter_stage("probing", deps, stage_adapters)),
        "telemetry-sync": Stage("telemetry-sync", _adapter_stage("telemetry-sync", deps, stage_adapters)),
        "quota-sync": Stage("quota-sync", _adapter_stage("quota-sync", deps, stage_adapters)),
        "hermes-inventory": Stage("hermes-inventory", _adapter_stage("hermes-inventory", deps, stage_adapters)),
        "role-lifecycle": Stage("role-lifecycle", _adapter_stage("role-lifecycle", deps, stage_adapters)),
        "role-scoring": Stage("role-scoring", _adapter_stage("role-scoring", deps, stage_adapters)),
        "demand-forecast": Stage("demand-forecast", _adapter_stage("demand-forecast", deps, stage_adapters)),
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
    "research-quotas": "quota-research",
    "classify-access": "access-classification",
    "sync-metadata": "external-metadata-sync",
    "match-models": "model-matching",
    "probe-models": "probing",
    "sync-telemetry": "telemetry-sync",
    "sync-quotas": "quota-sync",
    "sync-hermes-inventory": "hermes-inventory",
    "reconcile-roles": "role-lifecycle",
    "score-roles": "role-scoring",
    "forecast-demand": "demand-forecast",
    "allocate": "allocation",
    "diff": "diff",
    "apply": "apply",
    # `rollback` selects the audit stage via stages_for_command (audit has no
    # command of its own); the top-level `rollback` CLI command is separately
    # special-cased in run_command to the dedicated revert path.
    "rollback": "audit",
}
