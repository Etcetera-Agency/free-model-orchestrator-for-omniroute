from __future__ import annotations

import argparse
import hashlib
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from psycopg.types.json import Jsonb

from fmo.access import classify_access
from fmo.allocation import allocate_globally, build_priority_combo, validate_plan
from fmo.applier import ComboApplier
from fmo.apply_guard import ApplyPreconditions, check_apply_preconditions
from fmo.config import StartupConfig
from fmo.external_metadata import ExternalMetadataError
from fmo.hermes_inventory import (
    HermesInventoryError,
    Inventory,
    assemble_inspector_prompt,
    build_hermes_inventory,
    read_hermes_command_sources,
    read_hermes_home,
    read_hermes_http_sources,
    run_inspector,
)
from fmo.llm_runtime import LlmProviderConfig, SharedInstructorRuntime, build_instructor_runtime
from fmo.matcher import match_model
from fmo.metadata_sync import sync_external_metadata
from fmo.omniroute import OmniRouteClient
from fmo.persistence import Database, Repository
from fmo.pipeline import CANONICAL_STAGE_NAMES, PipelineContext, PipelineRunner, PipelineRunResult, Stage, StageResult
from fmo.probes import probe_endpoint
from fmo.quota_manager import QuotaFetchError, fetch_live_quota_snapshot
from fmo.quota_research import research_quota_rule
from fmo.registry import RegistryFetchError, persist_free_registry_outcome, sync_live_free_registry
from fmo.scanner import CatalogFetchError, CatalogScanner, scan_live_omniroute_catalogs
from fmo.scoring import eligible_for_scoring, score_endpoint
from fmo.scheduler import Scheduler
from fmo.smart_review import ComboReviewResult, run_combo_review
from fmo.telemetry import sync_live_telemetry


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
StageAdapter = Callable[["StageDependencies", PipelineContext], StageResult]
HermesInventoryAdapter = Callable[[StartupConfig], object]


@dataclass(frozen=True)
class StageDependencies:
    repository: Repository | None
    omniroute_client: OmniRouteClient | None
    config: StartupConfig | None = None
    llm_runtime: SharedInstructorRuntime | None = None
    hermes_inventory_adapter: HermesInventoryAdapter | None = None


@dataclass(frozen=True)
class StageAdapters:
    registry_sync: RegistrySync = sync_live_free_registry
    catalog_scan: CatalogScan = field(default_factory=lambda: _scan_catalogs)
    stage_adapters: dict[str, StageAdapter] = field(default_factory=lambda: _production_stage_adapters())
    hermes_inventory: HermesInventoryAdapter | None = None
    instructor_from_openai: Any | None = None
    openai_client_factory: Any | None = None


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
    llm_runtime = build_production_llm_runtime(config, repository, adapters=selected_adapters)
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
        stages=build_canonical_stages(dependencies=dependencies, metadata_sync=metadata_sync, adapters=selected_adapters),
        cron=config.hermes_inventory_cron,
    )


def build_production_llm_runtime(
    config: StartupConfig,
    repository: Repository,
    *,
    adapters: StageAdapters | None = None,
) -> SharedInstructorRuntime:
    selected_adapters = adapters or StageAdapters()
    provider = LlmProviderConfig(
        base_url=urljoin(config.omniroute_url.rstrip("/") + "/", "v1"),
        api_key=config.omniroute_api_key or "",
    )
    return build_instructor_runtime(
        provider=provider,
        model_resolver=lambda: select_llm_model(repository, config),
        instructor_from_openai=selected_adapters.instructor_from_openai,
        openai_client_factory=selected_adapters.openai_client_factory,
    )


def select_llm_model(repository: Repository, config: StartupConfig) -> str | None:
    if repository is not None:
        with repository.database.transaction() as transaction:
            row = transaction.execute(
                """
                SELECT f.provider_model_id
                FROM free_model_definitions f
                JOIN provider_accounts pa
                  ON pa.omniroute_connection_id = COALESCE(f.omniroute_pool_key, f.provider_id)
                JOIN provider_endpoints pe
                  ON pe.provider_account_id = pa.id
                 AND pe.provider_model_id = f.provider_model_id
                JOIN endpoint_access_states eas
                  ON eas.endpoint_id = pe.id
                JOIN artificial_analysis_model_metrics aa
                  ON aa.canonical_model_id = pe.canonical_model_id
                LEFT JOIN LATERAL (
                  SELECT status
                  FROM endpoint_health_observations health
                  WHERE health.endpoint_id = pe.id
                  ORDER BY health.observed_at DESC
                  LIMIT 1
                ) latest_health ON true
                WHERE f.status = 'active'
                  AND eas.status = 'confirmed'
                  AND COALESCE(
                    (eas.effective_remaining ->> 'requests')::numeric,
                    (eas.effective_remaining ->> 'tokens')::numeric,
                    0
                  ) > 0
                  AND COALESCE(latest_health.status, 'active') = 'active'
                ORDER BY aa.intelligence_index DESC NULLS LAST, f.provider_model_id
                LIMIT 1
                """
            ).fetchone()
            if row is not None:
                return row["provider_model_id"]
    if config.llm_bootstrap_model_id and config.llm_bootstrap_confirmed_free:
        return config.llm_bootstrap_model_id
    return None


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
        "model-matching": Stage("model-matching", _adapter_stage("model-matching", deps, stage_adapters)),
        "quota-research": Stage("quota-research", _adapter_stage("quota-research", deps, stage_adapters)),
        "access-classification": Stage("access-classification", _adapter_stage("access-classification", deps, stage_adapters)),
        "probing": Stage("probing", _adapter_stage("probing", deps, stage_adapters)),
        "telemetry-sync": Stage("telemetry-sync", _adapter_stage("telemetry-sync", deps, stage_adapters)),
        "quota-sync": Stage("quota-sync", _adapter_stage("quota-sync", deps, stage_adapters)),
        "hermes-inventory": Stage("hermes-inventory", _adapter_stage("hermes-inventory", deps, stage_adapters)),
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
    adapter = adapters.stage_adapters.get(name, _not_implemented_stage(name))

    def run(context: PipelineContext) -> StageResult:
        return adapter(dependencies, context)

    return run


def _not_implemented_stage(name: str) -> StageAdapter:
    def run(_dependencies: StageDependencies, _context: PipelineContext) -> StageResult:
        return StageResult(
            status="not_implemented",
            idempotency_key=f"{name}:not-implemented",
            reason=f"{name} adapter is not wired",
            details={"adapter": name, "effect": None},
        )

    return run


def _production_stage_adapters() -> dict[str, StageAdapter]:
    return {
        "model-matching": _model_matching_stage,
        "quota-research": _quota_research_stage,
        "access-classification": _access_classification_stage,
        "probing": _probing_stage,
        "telemetry-sync": _telemetry_sync_stage,
        "quota-sync": _quota_sync_stage,
        "hermes-inventory": _hermes_inventory_stage,
        "role-scoring": _role_scoring_stage,
        "allocation": _allocation_stage,
        "diff": _diff_stage,
        "apply": _apply_stage,
        "audit": _audit_stage,
    }


def _model_matching_stage(_dependencies: StageDependencies, context: PipelineContext) -> StageResult:
    with context.repository.database.transaction() as transaction:
        endpoints = transaction.execute(
            """
            SELECT pe.id, pe.provider_model_id
            FROM provider_endpoints pe
            WHERE pe.removed_at IS NULL
            ORDER BY pe.provider_model_id
            """
        ).fetchall()
        canonical_slugs = {
            row["canonical_slug"]
            for row in transaction.execute("SELECT canonical_slug FROM canonical_models").fetchall()
        }
        provider_catalog_ids = {row["provider_model_id"] for row in endpoints}
        matched = 0
        for endpoint in endpoints:
            result = match_model(
                endpoint["provider_model_id"],
                canonical_slugs=canonical_slugs,
                provider_catalog_ids=provider_catalog_ids,
            )
            status = "auto_use" if result.auto_use else "review_required"
            canonical_id = None
            if result.auto_use:
                slug = _canonical_slug(endpoint["provider_model_id"])
                model = context.repository.canonical_models.upsert(transaction, canonical_slug=slug)
                canonical_slugs.add(slug)
                canonical_id = model["id"]
                matched += 1
                transaction.execute(
                    "UPDATE provider_endpoints SET canonical_model_id = %(model_id)s WHERE id = %(endpoint_id)s",
                    {"model_id": canonical_id, "endpoint_id": endpoint["id"]},
                )
            transaction.execute(
                """
                INSERT INTO model_match_candidates (
                  endpoint_id, canonical_model_id, method, confidence, status, evidence
                )
                VALUES (
                  %(endpoint_id)s, %(canonical_model_id)s, %(method)s,
                  %(confidence)s, %(status)s, %(evidence)s
                )
                """,
                {
                    "endpoint_id": endpoint["id"],
                    "canonical_model_id": canonical_id,
                    "method": result.method.value,
                    "confidence": result.confidence,
                    "status": status,
                    "evidence": Jsonb({"provider_model_id": endpoint["provider_model_id"]}),
                },
            )
    if endpoints and matched == 0:
        return StageResult(status="validation_failed", reason="no_model_matches", details={"adapter": "model-matching", "effect": None})
    return _effect_result("model-matching", changed=matched > 0)


def _quota_research_stage(dependencies: StageDependencies, context: PipelineContext) -> StageResult:
    if dependencies.omniroute_client is None:
        return StageResult(status="external_dependency_failed", reason="omniroute_client_required")
    with context.repository.database.transaction() as transaction:
        endpoints = transaction.execute(
            """
            SELECT pe.id, pe.provider_model_id, pa.id AS account_id, p.id AS provider_id,
                   p.omniroute_provider_id
            FROM provider_endpoints pe
            JOIN provider_accounts pa ON pa.id = pe.provider_account_id
            JOIN providers p ON p.id = pa.provider_id
            WHERE pe.canonical_model_id IS NOT NULL
            ORDER BY pe.provider_model_id
            """
        ).fetchall()
    written = 0
    today = datetime.now(timezone.utc)
    for endpoint in endpoints:
        result = research_quota_rule(
            dependencies.omniroute_client,
            provider=endpoint["omniroute_provider_id"],
            model_id=endpoint["provider_model_id"],
            today=today,
            summary_confidence_cap=0.70,
            instructor_call=dependencies.llm_runtime,
        )
        if result.error is not None:
            return StageResult(status="external_dependency_failed", reason=result.error.reason)
        if result.snapshot is None or result.rule is None:
            return StageResult(status="partial_stale", reason="quota_rule_missing")
        rule = result.rule
        claim = rule.claim
        with context.repository.database.transaction() as transaction:
            snapshot = context.repository.snapshots.store_quota_source(
                transaction,
                source_url=result.snapshot.evidence_urls[0] if result.snapshot.evidence_urls else result.snapshot.query,
                source_type="summary",
                payload={
                    "query": result.snapshot.query,
                    "answer_text": result.snapshot.answer_text,
                    "evidence_urls": list(result.snapshot.evidence_urls),
                },
            )
            context.repository.quota_rules.upsert(
                transaction,
                provider_id=endpoint["provider_id"],
                provider_account_id=endpoint["account_id"],
                source_snapshot_id=snapshot["id"],
                model_pattern=endpoint["provider_model_id"],
                access_type="free_quota",
                limits={claim.metric: claim.amount, "window": claim.window},
                reset_policy={"window": claim.window},
                hard_stop_capable=claim.hard_stop,
                confidence=rule.confidence,
                status="active",
                rule_hash=_hash_parts(str(endpoint["id"]), snapshot["content_hash"], str(rule.confidence)),
            )
        written += 1
    return _effect_result("quota-research", changed=written > 0)


def _access_classification_stage(_dependencies: StageDependencies, context: PipelineContext) -> StageResult:
    with context.repository.database.transaction() as transaction:
        rows = transaction.execute(
            """
            SELECT DISTINCT ON (pe.id)
                   pe.id AS endpoint_id, pe.provider_account_id, pe.provider_model_id,
                   p.omniroute_provider_id, qr.id AS quota_rule_id, qr.limits,
                   qr.reset_policy, qr.hard_stop_capable, qr.confidence
            FROM provider_endpoints pe
            JOIN provider_accounts pa ON pa.id = pe.provider_account_id
            JOIN providers p ON p.id = pa.provider_id
            LEFT JOIN quota_rules qr
              ON qr.provider_id = p.id
             AND qr.model_pattern = pe.provider_model_id
             AND qr.status = 'active'
            WHERE pe.canonical_model_id IS NOT NULL
            ORDER BY pe.id, qr.created_at DESC NULLS LAST
            """
        ).fetchall()
        if any(row["quota_rule_id"] is None for row in rows):
            return StageResult(status="partial_stale", reason="quota_rule_missing")
        written = 0
        for row in rows:
            limit = _quota_limit(row["limits"])
            reset_at = datetime.now(timezone.utc) + timedelta(days=1)
            evidence = {
                "quota_rule": True,
                "limit": limit,
                "remaining": limit,
                "reset_at": reset_at.isoformat(),
                "hard_stop": row["hard_stop_capable"],
                "confidence": float(row["confidence"]),
            }
            decision = classify_access(evidence)
            status = _canonical_access_status(decision.status)
            transaction.execute(
                """
                INSERT INTO endpoint_access_states (
                  endpoint_id, quota_rule_id, status, reason_code, effective_remaining,
                  reset_at, hard_stop_capable, evidence
                )
                VALUES (
                  %(endpoint_id)s, %(quota_rule_id)s, %(status)s, %(reason_code)s,
                  %(effective_remaining)s, %(reset_at)s, %(hard_stop_capable)s, %(evidence)s
                )
                ON CONFLICT (endpoint_id)
                DO UPDATE SET
                  quota_rule_id = EXCLUDED.quota_rule_id,
                  status = EXCLUDED.status,
                  reason_code = EXCLUDED.reason_code,
                  effective_remaining = EXCLUDED.effective_remaining,
                  reset_at = EXCLUDED.reset_at,
                  hard_stop_capable = EXCLUDED.hard_stop_capable,
                  evidence = EXCLUDED.evidence,
                  classified_at = now()
                """,
                {
                    "endpoint_id": row["endpoint_id"],
                    "quota_rule_id": row["quota_rule_id"],
                    "status": status,
                    "reason_code": decision.reason_code,
                    "effective_remaining": Jsonb({"requests": limit}),
                    "reset_at": reset_at,
                    "hard_stop_capable": row["hard_stop_capable"],
                    "evidence": Jsonb({**evidence, "free_access": status == "confirmed"}),
                },
            )
            group = transaction.execute(
                """
                INSERT INTO quota_attribution_groups (
                  provider_id, scope_type, scope_key, status, source, limit_type,
                  request_limit, reset_rule_json, confidence, capacity_weight, evidence_json
                )
                VALUES (
                  %(provider_id)s, 'account', %(scope_key)s, %(status)s, 'quota-research',
                  'requests', %(request_limit)s, %(reset_rule_json)s, %(confidence)s,
                  %(capacity_weight)s, %(evidence_json)s
                )
                RETURNING *
                """,
                {
                    "provider_id": row["omniroute_provider_id"],
                    "scope_key": str(row["provider_account_id"]),
                    "status": status,
                    "request_limit": limit,
                    "reset_rule_json": Jsonb(row["reset_policy"]),
                    "confidence": row["confidence"],
                    "capacity_weight": _capacity_weight(status),
                    "evidence_json": Jsonb([evidence]),
                },
            ).fetchone()
            transaction.execute(
                """
                INSERT INTO endpoint_quota_attribution (
                  endpoint_id, account_or_connection_id, quota_attribution_group_id,
                  attribution_status, evidence_json
                )
                VALUES (
                  %(endpoint_id)s, %(account_id)s, %(group_id)s,
                  %(status)s, %(evidence_json)s
                )
                """,
                {
                    "endpoint_id": row["endpoint_id"],
                    "account_id": str(row["provider_account_id"]),
                    "group_id": group["id"],
                    "status": status,
                    "evidence_json": Jsonb([evidence]),
                },
            )
            transaction.execute(
                "UPDATE provider_endpoints SET access_status = %(status)s WHERE id = %(endpoint_id)s",
                {"status": status, "endpoint_id": row["endpoint_id"]},
            )
            written += 1
    return _effect_result("access-classification", changed=written > 0)


def _probing_stage(dependencies: StageDependencies, context: PipelineContext) -> StageResult:
    if dependencies.omniroute_client is None:
        return StageResult(status="external_dependency_failed", reason="omniroute_client_required")
    with context.repository.database.transaction() as transaction:
        rows = transaction.execute(
            """
            SELECT pe.id, pe.provider_model_id, pe.capabilities, p.omniroute_provider_id,
                   eas.status, eas.effective_remaining
            FROM provider_endpoints pe
            JOIN provider_accounts pa ON pa.id = pe.provider_account_id
            JOIN providers p ON p.id = pa.provider_id
            JOIN endpoint_access_states eas ON eas.endpoint_id = pe.id
            WHERE eas.status = 'confirmed'
            ORDER BY pe.provider_model_id
            """
        ).fetchall()
    written = 0
    for row in rows:
        if _remaining_requests(row["effective_remaining"]) <= 0:
            continue
        started_at = datetime.now(timezone.utc)
        result = probe_endpoint(
            dependencies.omniroute_client,
            provider=row["omniroute_provider_id"],
            model=row["provider_model_id"],
            capabilities=dict(row["capabilities"] or {}),
        )
        finished_at = datetime.now(timezone.utc)
        request_hash = _hash_parts(str(row["id"]), started_at.date().isoformat(), "basic")
        with context.repository.database.transaction() as transaction:
            context.repository.probes.record(
                transaction,
                endpoint_id=row["id"],
                suite_version="production-v1",
                probe_type="basic",
                request_hash=request_hash,
                passed=result.passed,
                http_status=200 if result.passed else 500,
                started_at=started_at,
                finished_at=finished_at,
                details={"suites": list(result.suites), "reserved_capacity": True},
            )
            transaction.execute(
                "UPDATE provider_endpoints SET probe_status = %(status)s WHERE id = %(endpoint_id)s",
                {"status": "passed" if result.passed else "failed", "endpoint_id": row["id"]},
            )
        written += 1
    return _effect_result("probing", changed=written > 0)


def _telemetry_sync_stage(dependencies: StageDependencies, context: PipelineContext) -> StageResult:
    if dependencies.omniroute_client is None:
        return StageResult(status="external_dependency_failed", reason="omniroute_client_required")
    snapshot = sync_live_telemetry(dependencies.omniroute_client)
    if snapshot.errors:
        return StageResult(status="external_dependency_failed", reason=snapshot.errors[0].reason)
    observed_at = datetime.now(timezone.utc)
    written = 0
    with context.repository.database.transaction() as transaction:
        for provider_id, metric in snapshot.provider_metrics.items():
            provider = transaction.execute(
                "SELECT id FROM providers WHERE omniroute_provider_id = %(provider_id)s LIMIT 1",
                {"provider_id": provider_id},
            ).fetchone()
            if provider is None:
                continue
            _insert_health_observation(
                transaction,
                provider_id=provider["id"],
                endpoint_id=None,
                status="active",
                metric=metric,
                observed_at=observed_at,
            )
            written += 1
        for (provider_id, model_id), metric in snapshot.model_metrics.items():
            endpoint = transaction.execute(
                """
                SELECT pe.id
                FROM provider_endpoints pe
                JOIN provider_accounts pa ON pa.id = pe.provider_account_id
                JOIN providers p ON p.id = pa.provider_id
                WHERE p.omniroute_provider_id = %(provider_id)s
                  AND pe.provider_model_id = %(model_id)s
                LIMIT 1
                """,
                {"provider_id": provider_id, "model_id": model_id},
            ).fetchone()
            if endpoint is None:
                continue
            _insert_health_observation(
                transaction,
                provider_id=None,
                endpoint_id=endpoint["id"],
                status="active" if metric.failure_count == 0 else "degraded",
                metric=metric,
                observed_at=observed_at,
            )
            written += 1
    return _effect_result("telemetry-sync", changed=written > 0)


def _quota_sync_stage(dependencies: StageDependencies, context: PipelineContext) -> StageResult:
    if dependencies.omniroute_client is None:
        return StageResult(status="external_dependency_failed", reason="omniroute_client_required")
    try:
        snapshot = fetch_live_quota_snapshot(dependencies.omniroute_client)
    except QuotaFetchError as exc:
        return StageResult(status="partial_stale", reason=exc.reason)
    written = 0
    with context.repository.database.transaction() as transaction:
        for quota in snapshot.quotas.values():
            account = transaction.execute(
                """
                SELECT pa.id, pa.quota_pool_id, p.omniroute_provider_id
                FROM provider_accounts pa
                JOIN providers p ON p.id = pa.provider_id
                WHERE p.omniroute_provider_id = %(provider_id)s
                  AND pa.omniroute_connection_id = %(connection_id)s
                LIMIT 1
                """,
                {"provider_id": quota.provider, "connection_id": quota.connection_id},
            ).fetchone()
            if account is None:
                continue
            quota_pool_id = account["quota_pool_id"] or _ensure_quota_pool(
                transaction,
                quota.provider,
                quota.connection_id,
                account["id"],
            )
            used = None if quota.limit is None or quota.remaining is None else quota.limit - quota.remaining
            transaction.execute(
                """
                INSERT INTO quota_observations (
                  quota_pool_id, provider_account_id, source, metric, limit_value,
                  used_value, remaining_value, reset_at, raw_payload, observed_at
                )
                VALUES (
                  %(quota_pool_id)s, %(provider_account_id)s, 'omniroute', 'requests',
                  %(limit_value)s, %(used_value)s, %(remaining_value)s, %(reset_at)s,
                  %(raw_payload)s, %(observed_at)s
                )
                """,
                {
                    "quota_pool_id": quota_pool_id,
                    "provider_account_id": account["id"],
                    "limit_value": quota.limit,
                    "used_value": used,
                    "remaining_value": quota.remaining,
                    "reset_at": quota.reset_at,
                    "raw_payload": Jsonb({"provider": quota.provider, "connectionId": quota.connection_id}),
                    "observed_at": snapshot.observed_at,
                },
            )
            transaction.execute(
                """
                UPDATE endpoint_access_states eas
                SET effective_remaining = %(effective_remaining)s,
                    reset_at = %(reset_at)s,
                    classified_at = now()
                FROM provider_endpoints pe
                WHERE eas.endpoint_id = pe.id
                  AND pe.provider_account_id = %(provider_account_id)s
                """,
                {
                    "effective_remaining": Jsonb({"requests": quota.remaining}),
                    "reset_at": quota.reset_at,
                    "provider_account_id": account["id"],
                },
            )
            written += 1
    return _effect_result("quota-sync", changed=written > 0)


def _hermes_inventory_stage(dependencies: StageDependencies, context: PipelineContext) -> StageResult:
    if dependencies.config is None:
        return StageResult(status="validation_failed", reason="startup_config_required")
    try:
        inventory = _read_hermes_inventory(dependencies)
    except (ValueError, HermesInventoryError) as exc:
        return StageResult(status="validation_failed", reason=str(exc))
    source_hash = _hash_parts(
        dependencies.config.hermes_inventory_mode,
        *[
            _hash_parts(consumer.role_id, consumer.consumer_type, consumer.consumer, consumer.cadence, str(consumer.calls_per_run))
            for consumer in inventory.consumers
        ],
    )
    forecast = _run_hermes_inspector(dependencies, inventory)
    by_role: dict[str, float] = {}
    for consumer in inventory.consumers:
        by_role[consumer.role_id] = by_role.get(consumer.role_id, 0.0) + float(consumer.calls_per_run)
    if forecast is not None:
        by_role[forecast.role] = max(by_role.get(forecast.role, 0.0), float(forecast.expected_calls))
    with context.repository.database.transaction() as transaction:
        inventory_run = context.repository.role_consumers.start_inventory_run(
            transaction,
            source_mode=dependencies.config.hermes_inventory_mode,
            trigger_type="manual" if context.config.get("command") == "sync-hermes-inventory" else "daily",
            source_hash=source_hash,
        )
        for role_id, calls in by_role.items():
            existing_role = transaction.execute(
                "SELECT 1 FROM roles WHERE id = %(role_id)s",
                {"role_id": role_id},
            ).fetchone()
            context.repository.roles.upsert(
                transaction,
                role_id=role_id,
                requirements={"capabilities": []},
                expected_load={"requests": calls},
                criticality=1,
            )
            if existing_role is None:
                transaction.execute(
                    """
                    UPDATE roles
                    SET role_lifecycle_status = 'bootstrap_pending'
                    WHERE id = %(role_id)s
                    """,
                    {"role_id": role_id},
                )
        for consumer in inventory.consumers:
            context.repository.role_consumers.upsert(
                transaction,
                role_id=consumer.role_id,
                consumer_type=consumer.consumer_type,
                consumer_key=consumer.consumer,
                cadence=consumer.cadence,
                calls_per_run=consumer.calls_per_run,
                source_hash=source_hash,
            )
        context.repository.role_consumers.complete_inventory_run(
            transaction,
            run_id=inventory_run["id"],
            roles_found=len(by_role),
            consumers_found=len(inventory.consumers),
        )
    if not inventory.consumers:
        return StageResult(status="partial_stale", reason="hermes_inventory_empty")
    return _effect_result("hermes-inventory", changed=True)


def _read_hermes_inventory(dependencies: StageDependencies) -> Inventory:
    if dependencies.config is None:
        raise ValueError("startup_config_required")
    mode = dependencies.config.hermes_inventory_mode
    if dependencies.hermes_inventory_adapter is not None:
        return dependencies.hermes_inventory_adapter(dependencies.config)
    if mode == "filesystem":
        if not dependencies.config.hermes_home:
            raise ValueError("HERMES_HOME is required")
        return read_hermes_home(Path(dependencies.config.hermes_home or ""))
    if mode == "command":
        if not dependencies.config.hermes_inventory_command:
            raise ValueError("HERMES_INVENTORY_COMMAND is required")
        sources = read_hermes_command_sources(str(dependencies.config.hermes_inventory_command or "").split())
        return build_hermes_inventory(**sources)
    if mode == "http":
        if not dependencies.config.hermes_inventory_url:
            raise ValueError("HERMES_INVENTORY_URL is required")
        sources = read_hermes_http_sources(str(dependencies.config.hermes_inventory_url or ""))
        return build_hermes_inventory(**sources)
    raise ValueError("HERMES_INVENTORY_MODE is invalid")


def _run_hermes_inspector(dependencies: StageDependencies, inventory):
    if dependencies.llm_runtime is None:
        return None
    prompt = assemble_inspector_prompt(inventory, changes=[], secrets={})
    try:
        return run_inspector(dependencies.llm_runtime, prompt)
    except Exception:
        return None


def _role_scoring_stage(_dependencies: StageDependencies, context: PipelineContext) -> StageResult:
    with context.repository.database.transaction() as transaction:
        roles = transaction.execute("SELECT id, requirements FROM roles ORDER BY id").fetchall()
        endpoints = transaction.execute(
            """
            SELECT pe.id, pe.capabilities, pe.provider_account_id, pe.access_status,
                   pe.probe_status, eas.effective_remaining
            FROM provider_endpoints pe
            JOIN endpoint_access_states eas ON eas.endpoint_id = pe.id
            WHERE pe.access_status = 'confirmed'
              AND pe.probe_status = 'passed'
            ORDER BY pe.provider_model_id
            """
        ).fetchall()
        written = 0
        for role in roles:
            required = set((role["requirements"] or {}).get("capabilities", []))
            for endpoint in endpoints:
                eligibility = eligible_for_scoring(
                    {
                        "access": "free_quota_available",
                        "basic_probe": endpoint["probe_status"] == "passed",
                        "quota": _remaining_requests(endpoint["effective_remaining"]),
                        "matched": True,
                        "breaker": "closed",
                        "capabilities": set((endpoint["capabilities"] or {}).keys()),
                    },
                    required_capabilities=required,
                )
                score = score_endpoint(
                    {
                        "benchmark_fit": 1.0,
                        "capability_fit": 1.0 if eligibility.eligible else 0.0,
                        "health": 1.0,
                        "latency": 1.0,
                        "quota_headroom": min(_remaining_requests(endpoint["effective_remaining"]) / 100, 1.0),
                        "stability": 1.0,
                    }
                )
                context.repository.scores.upsert(
                    transaction,
                    role_id=role["id"],
                    endpoint_id=endpoint["id"],
                    score_version="production-v1",
                    total_score=score.total,
                    component_scores=score.components,
                    eligibility=eligibility.eligible,
                    rejection_reasons=[] if eligibility.eligible else [eligibility.reason or "unknown"],
                    input_state_hash=_hash_parts(str(role["id"]), str(endpoint["id"]), str(score.total)),
                )
                written += 1
    return _effect_result("role-scoring", changed=written > 0)


def _allocation_stage(_dependencies: StageDependencies, context: PipelineContext) -> StageResult:
    with context.repository.database.transaction() as transaction:
        roles = transaction.execute("SELECT id, expected_load FROM roles ORDER BY id").fetchall()
        score_rows = transaction.execute(
            """
            SELECT DISTINCT ON (rs.role_id, rs.endpoint_id)
                   rs.role_id, rs.endpoint_id, rs.total_score, pe.provider_account_id,
                   eas.effective_remaining
            FROM role_scores rs
            JOIN provider_endpoints pe ON pe.id = rs.endpoint_id
            JOIN endpoint_access_states eas ON eas.endpoint_id = pe.id
            WHERE rs.eligibility = true
            ORDER BY rs.role_id, rs.endpoint_id, rs.calculated_at DESC
            """
        ).fetchall()
        consumer_demand = {
            row["role_id"]: float(row["calls"])
            for row in transaction.execute(
                """
                SELECT role_id, SUM(calls_per_run) AS calls
                FROM role_consumers
                WHERE active = true
                GROUP BY role_id
                """
            ).fetchall()
        }
        demand = {
            role["id"]: consumer_demand.get(role["id"], float((role["expected_load"] or {}).get("requests", 1)))
            for role in roles
        }
        endpoints = [
            {
                "id": str(row["endpoint_id"]),
                "pool": str(row["provider_account_id"]),
                "score": float(row["total_score"]),
                "capacity": _remaining_requests(row["effective_remaining"]),
            }
            for row in score_rows
        ]
        plan = allocate_globally([role["id"] for role in roles], endpoints, demand)
        pool_reports = {
            pool: {
                "usage": usage,
                "capacity": max((endpoint["capacity"] for endpoint in endpoints if endpoint["pool"] == pool), default=0),
            }
            for pool, usage in plan.pool_usage.items()
        }
        written = 0
        for role in roles:
            allocation = plan.allocations.get(role["id"])
            role_scores = [endpoint for endpoint in endpoints if allocation is None or endpoint["id"] == allocation.endpoint_id]
            validation = validate_plan(pool_reports or {"empty": {"usage": 0, "capacity": 0}}, role_has_primary=allocation is not None)
            targets = []
            if allocation is not None:
                combo = build_priority_combo(role["id"], role_scores, per_pool_cap=2)
                targets = [
                    {"endpoint_id": endpoint_id, "priority": index + 1}
                    for index, endpoint_id in enumerate(combo.endpoints)
                ]
            context.repository.allocation_plans.upsert(
                transaction,
                role_id=role["id"],
                status="planned" if validation.apply else "degraded",
                targets=targets,
                constraint_report={
                    "apply": validation.apply,
                    "reason": validation.reason,
                    "role_status": validation.role_status,
                    "pool_reports": pool_reports,
                },
                input_state_hash=_hash_parts(role["id"], str(targets), str(pool_reports)),
            )
            written += 1
    return _effect_result("allocation", changed=written > 0)


def _diff_stage(dependencies: StageDependencies, context: PipelineContext) -> StageResult:
    current = _read_current_combos(dependencies.omniroute_client)
    with context.repository.database.transaction() as transaction:
        plans = transaction.execute(
            """
            SELECT DISTINCT ON (role_id) role_id, targets
            FROM allocation_plans
            ORDER BY role_id, created_at DESC
            """
        ).fetchall()
        written = 0
        for plan in plans:
            combo_id = f"fmo-{plan['role_id']}"
            desired = [target["endpoint_id"] for target in plan["targets"]]
            before = current.get(combo_id, [])
            diff = {
                "combo_id": combo_id,
                "before": before,
                "after": desired,
                "add": [endpoint_id for endpoint_id in desired if endpoint_id not in before],
                "remove": [endpoint_id for endpoint_id in before if endpoint_id not in desired],
            }
            review = _review_diff(dependencies, diff)
            context.repository.combo_snapshots.upsert(
                transaction,
                role_id=plan["role_id"],
                omniroute_combo_id=combo_id,
                state_hash=_hash_parts(combo_id, str(diff)),
                state_json={**diff, "advisory_review": _review_payload(review)},
                phase="diff",
                run_id=context.run_id,
            )
            written += 1
    return _effect_result("diff", changed=written > 0)


def _review_diff(dependencies: StageDependencies, diff: dict[str, Any]) -> ComboReviewResult:
    if dependencies.config is not None and dependencies.config.llm_smart_review_call_limit == 0:
        return run_combo_review(lambda _payload: {}, deterministic_combo={}, trigger=False)
    if dependencies.llm_runtime is None:
        return ComboReviewResult(status="failed", valid_diffs=[], rejected=[])
    deterministic_combo = {str(diff["combo_id"]): list(diff.get("after", []))}
    return run_combo_review(dependencies.llm_runtime, deterministic_combo=deterministic_combo, trigger=True)


def _review_payload(review: ComboReviewResult) -> dict[str, Any]:
    return {
        "status": review.status,
        "valid_diffs": review.valid_diffs,
        "rejected": review.rejected,
    }


def _apply_stage(dependencies: StageDependencies, context: PipelineContext) -> StageResult:
    if dependencies.omniroute_client is None:
        return StageResult(status="external_dependency_failed", reason="omniroute_client_required")
    with context.repository.database.transaction() as transaction:
        diffs = transaction.execute(
            """
            SELECT DISTINCT ON (omniroute_combo_id) id, role_id, omniroute_combo_id, state_json
            FROM combo_snapshots
            WHERE phase = 'diff'
              AND omniroute_combo_id LIKE 'fmo-%'
            ORDER BY omniroute_combo_id, created_at DESC
            """
        ).fetchall()
    try:
        check_apply_preconditions(
            ApplyPreconditions(
                db_available=True,
                snapshot_saved=bool(diffs),
                desired_state_valid=all(isinstance(diff["state_json"].get("after"), list) for diff in diffs),
                quota_safe=True,
                probes_passed=True,
            )
        )
    except ValueError as exc:
        return StageResult(status="unsafe_to_apply", reason=str(exc))

    current = _read_current_combos(dependencies.omniroute_client)
    applier = ComboApplier(current={combo_id: list(models) for combo_id, models in current.items()})
    combo_test_called = False
    applied = []
    for diff in diffs:
        combo_id = diff["omniroute_combo_id"]
        before = list(diff["state_json"].get("before", []))
        desired = list(diff["state_json"].get("after", []))
        if not combo_id.startswith("fmo-"):
            continue
        expected_hash = applier.state_hash(combo_id)
        dependencies.omniroute_client.post(f"/api/combos/{combo_id}", {"models": desired})
        smoke_ok = _smoke_combo(dependencies.omniroute_client, combo_id)
        combo_test_called = True
        applier.apply(combo_id, desired, expected_hash=expected_hash, smoke_ok=smoke_ok)
        if not smoke_ok:
            try:
                dependencies.omniroute_client.post(f"/api/combos/{combo_id}", {"models": before})
            except Exception:
                return StageResult(status="rollback_failed", reason="rollback_failed", details={"combo_test_called": True})
            return StageResult(status="apply_failed_rolled_back", reason="smoke_failed", details={"combo_test_called": True})
        applied.append((diff, before, desired))
    with context.repository.database.transaction() as transaction:
        for diff, before, desired in applied:
            context.repository.combo_snapshots.upsert(
                transaction,
                role_id=diff["role_id"],
                omniroute_combo_id=diff["omniroute_combo_id"],
                state_hash=_hash_parts(diff["omniroute_combo_id"], str(desired), "applied"),
                state_json={"before": before, "after": desired},
                phase="applied",
                run_id=context.run_id,
            )
    result = _effect_result("apply", changed=bool(applied))
    return StageResult(
        status=result.status,
        idempotency_key=result.idempotency_key,
        changed=result.changed,
        details={**result.details, "combo_test_called": combo_test_called},
    )


def _audit_stage(dependencies: StageDependencies, context: PipelineContext) -> StageResult:
    current = _read_current_combos(dependencies.omniroute_client)
    with context.repository.database.transaction() as transaction:
        applied = transaction.execute(
            """
            SELECT DISTINCT ON (omniroute_combo_id) role_id, omniroute_combo_id, state_json
            FROM combo_snapshots
            WHERE phase = 'applied'
            ORDER BY omniroute_combo_id, created_at DESC
            """
        ).fetchall()
        written = 0
        for snapshot in applied:
            combo_id = snapshot["omniroute_combo_id"]
            after = list(snapshot["state_json"].get("after", []))
            live = current.get(combo_id, after)
            action = "drift_detected" if live != after else "apply_audited"
            context.repository.audit.record(
                transaction,
                run_id=context.run_id,
                entity_type="combo",
                entity_id=combo_id,
                action=action,
                before_json={"expected": after},
                after_json={"live": live},
                reason_codes=[action],
                source_refs=[{"source": "apply-stage", "role_id": snapshot["role_id"]}],
            )
            written += 1
    return _effect_result("audit", changed=written > 0)


def _smoke_combo(client: Any, combo_id: str) -> bool:
    response = client.post(
        "/v1/chat/completions",
        {"model": combo_id, "messages": [{"role": "user", "content": "Return ok"}]},
    )
    return response.get("status_code") == 200 and bool(response.get("content", "ok"))


def _read_current_combos(client: Any | None) -> dict[str, list[str]]:
    if client is None or not hasattr(client, "get"):
        return {}
    payload = client.get("/api/combos")
    combos = payload.get("combos", []) if isinstance(payload, dict) else []
    return {
        str(combo["id"]): [str(model) for model in combo.get("models", [])]
        for combo in combos
        if isinstance(combo, dict) and str(combo.get("id", "")).startswith("fmo-")
    }


def _insert_health_observation(
    transaction: Any,
    *,
    provider_id: Any | None,
    endpoint_id: Any | None,
    status: str,
    metric: Any,
    observed_at: datetime,
) -> None:
    success_rate = None
    error_rate = None
    if metric.requests:
        error_rate = metric.failure_count / metric.requests
        success_rate = 1 - error_rate
    transaction.execute(
        """
        INSERT INTO endpoint_health_observations (
          endpoint_id, provider_id, granularity, status, success_rate, error_rate,
          latency_p50_ms, latency_p95_ms, sample_count, observed_at
        )
        VALUES (
          %(endpoint_id)s, %(provider_id)s, %(granularity)s, %(status)s,
          %(success_rate)s, %(error_rate)s, %(latency_p50_ms)s, %(latency_p95_ms)s,
          %(sample_count)s, %(observed_at)s
        )
        """,
        {
            "endpoint_id": endpoint_id,
            "provider_id": provider_id,
            "granularity": metric.latency_granularity,
            "status": status,
            "success_rate": success_rate,
            "error_rate": error_rate,
            "latency_p50_ms": metric.avg_latency_ms,
            "latency_p95_ms": metric.p95_ms,
            "sample_count": metric.requests,
            "observed_at": observed_at,
        },
    )


def _ensure_quota_pool(transaction: Any, provider_id: str, connection_id: str, account_id: Any) -> Any:
    pool = transaction.execute(
        """
        INSERT INTO quota_pools (name, provider_group, reset_policy)
        VALUES (%(name)s, %(provider_group)s, %(reset_policy)s)
        ON CONFLICT (name)
        DO UPDATE SET provider_group = EXCLUDED.provider_group
        RETURNING id
        """,
        {
            "name": f"{provider_id}:{connection_id}:requests",
            "provider_group": provider_id,
            "reset_policy": Jsonb({"source": "omniroute"}),
        },
    ).fetchone()
    transaction.execute(
        "UPDATE provider_accounts SET quota_pool_id = %(quota_pool_id)s WHERE id = %(account_id)s",
        {"quota_pool_id": pool["id"], "account_id": account_id},
    )
    return pool["id"]


def _effect_result(stage_name: str, *, changed: bool) -> StageResult:
    effect = "repository_write" if changed else "idempotent_no_change"
    return StageResult(
        status="success",
        changed=changed,
        idempotency_key=f"{stage_name}:production",
        details={"adapter": stage_name, "effect": effect},
    )


def _canonical_slug(provider_model_id: str) -> str:
    return provider_model_id.lower().split("/")[-1].replace("_", "-")


def _hash_parts(*parts: str) -> str:
    return hashlib.sha256(":".join(parts).encode("utf-8")).hexdigest()


def _quota_limit(limits: Any) -> float:
    if isinstance(limits, dict):
        value = limits.get("requests", 0)
    else:
        value = limits["requests"]
    return float(value)


def _remaining_requests(effective_remaining: Any) -> float:
    if isinstance(effective_remaining, dict):
        value = effective_remaining.get("requests", 0)
    else:
        value = effective_remaining["requests"]
    return float(value or 0)


def _canonical_access_status(access_status: str) -> str:
    if access_status in {"free_unlimited", "free_quota_available"}:
        return "confirmed"
    if access_status == "free_promotional_available":
        return "inferred"
    return "unknown"


def _capacity_weight(status: str) -> float:
    if status == "confirmed":
        return 1.0
    if status == "inferred":
        return 0.5
    return 0.0


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
        combo_test_called=any(bool(stage["details"].get("combo_test_called")) for stage in result.stage_results),
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
    "sync-hermes-inventory": "hermes-inventory",
    "score-roles": "role-scoring",
    "allocate": "allocation",
    "diff": "diff",
    "apply": "apply",
    "rollback": "audit",
}
