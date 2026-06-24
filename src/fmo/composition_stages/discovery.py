from __future__ import annotations

from collections.abc import Callable
from typing import Any

from psycopg.types.json import Jsonb

from fmo.accounts import AccountFetchError
from fmo.external_metadata import ExternalMetadataError
from fmo.idempotency import canonical_slug
from fmo.matcher import match_model
from fmo.metadata_sync import MetadataSyncResult
from fmo.model_registration import register_new_free_models
from fmo.pipeline import PipelineContext, StageResult
from fmo.registry import RegistryFetchError, persist_free_registry_outcome
from fmo.scanner import CatalogFetchError, CatalogScanner, scan_live_omniroute_catalogs

from ._base import FreeModelChanges, StageAdapters, StageDependencies
from ._helpers import _effect_result, _omniroute_instance_id

MetadataSync = Callable[..., MetadataSyncResult]


def _ensure_named_quota_pool(transaction: Any, provider_id: str, pool_key: str) -> Any:
    from .quota import _ensure_named_quota_pool as ensure_named_quota_pool

    return ensure_named_quota_pool(transaction, provider_id, pool_key)


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


def _free_candidate_stage(
    dependencies: StageDependencies, adapters: StageAdapters
) -> Callable[[PipelineContext], StageResult]:
    def run(context: PipelineContext) -> StageResult:
        command = str(context.config.get("command") or "full")
        try:
            if command in {"sync-free-registry", "full"}:
                outcome = adapters.registry_sync(dependencies.omniroute_client)
                if dependencies.omniroute_client is not None:
                    register_new_free_models(
                        context.repository, dependencies.omniroute_client, outcome.free_models_payload
                    )
                persist_free_registry_outcome(context.repository, outcome)
            if command in {"scan-providers", "full"}:
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
            changed=command in {"sync-free-registry", "scan-providers", "full"},
            idempotency_key=f"free-candidate-discovery:{command}",
            details={"adapter": "free-candidate-discovery", "command": command},
        )

    return run


def _account_discovery_stage(
    dependencies: StageDependencies, adapters: StageAdapters
) -> Callable[[PipelineContext], StageResult]:
    def run(context: PipelineContext) -> StageResult:
        if dependencies.omniroute_client is None:
            return StageResult(status="external_dependency_failed", reason="omniroute_client_required")
        with context.repository.database.transaction() as transaction:
            previous_pools = _previous_account_pools(transaction)
        try:
            outcome = adapters.account_discovery(dependencies.omniroute_client, previous_pools=previous_pools)
        except AccountFetchError as exc:
            return StageResult(status="external_dependency_failed", reason=exc.reason)
        with context.repository.database.transaction() as transaction:
            written = _persist_account_discovery(context, transaction, outcome)
        return _effect_result("account-discovery", changed=written > 0)

    return run


def _previous_account_pools(transaction: Any) -> dict[str, str]:
    rows = transaction.execute(
        """
        SELECT omniroute_connection_id, qp.name AS pool_name
        FROM provider_accounts pa
        JOIN quota_pools qp ON qp.id = pa.quota_pool_id
        WHERE omniroute_connection_id IS NOT NULL
        """
    ).fetchall()
    return {str(row["omniroute_connection_id"]): str(row["pool_name"]) for row in rows}


def _persist_account_discovery(context: PipelineContext, transaction: Any, outcome: Any) -> int:
    accounts_by_connection = {}
    for connection in outcome.connections:
        provider_slug = str(connection.get("provider") or "unknown")
        connection_id = str(connection["id"])
        provider = context.repository.providers.upsert(
            transaction,
            omniroute_instance_id="default",
            omniroute_provider_id=provider_slug,
            provider_type=str(connection.get("authType") or connection.get("auth_type") or "unknown"),
        )
        account = context.repository.provider_accounts.upsert(
            transaction,
            provider_id=provider["id"],
            omniroute_connection_id=connection_id,
            external_account_ref=str(
                connection.get("external_account_ref")
                or connection.get("upstream_account_id")
                or connection.get("credential_fingerprint")
                or connection_id
            ),
            metadata=connection,
            enabled=bool(connection.get("enabled", True)),
        )
        pool = outcome.pools[connection_id]
        quota_pool_id = _ensure_named_quota_pool(transaction, provider_slug, pool.pool_key)
        transaction.execute(
            """
            UPDATE provider_accounts
            SET quota_independence_status = %(status)s,
                quota_pool_id = %(quota_pool_id)s
            WHERE id = %(account_id)s
            """,
            {"status": pool.independence_status, "quota_pool_id": quota_pool_id, "account_id": account["id"]},
        )
        transaction.execute(
            """
            INSERT INTO quota_pool_members (
              quota_pool_id, provider_account_id, membership_reason, confidence
            )
            VALUES (%(quota_pool_id)s, %(account_id)s, %(reason)s, %(confidence)s)
            """,
            {
                "quota_pool_id": quota_pool_id,
                "account_id": account["id"],
                "reason": str(connection.get("membership_reason") or "account-discovery"),
                "confidence": 1.0 if pool.independence_status == "confirmed" else 0.0,
            },
        )
        accounts_by_connection[connection_id] = account["id"]
    independent_count = len(
        {
            pool.pool_key
            for key, pool in outcome.pools.items()
            if key == pool.pool_key and pool.independence_status == "confirmed"
        }
    )
    transaction.execute(
        """
        INSERT INTO account_discovery_snapshots (
          run_id, raw_provider_count, active_connection_count,
          virtual_account_count, independent_quota_pool_count, snapshot_json
        )
        VALUES (
          %(run_id)s, %(raw_count)s, %(active_count)s,
          %(virtual_count)s, %(independent_count)s, %(snapshot)s
        )
        """,
        {
            "run_id": context.run_id,
            "raw_count": len(outcome.connections),
            "active_count": sum(1 for connection in outcome.connections if connection.get("enabled", True)),
            "virtual_count": len(accounts_by_connection),
            "independent_count": independent_count,
            "snapshot": Jsonb(
                {
                    "connections": outcome.connections,
                    "pools": {
                        key: {
                            "pool_key": pool.pool_key,
                            "independence_status": pool.independence_status,
                            "capacity": pool.capacity,
                        }
                        for key, pool in outcome.pools.items()
                    },
                    "rate_limits_available": outcome.rate_limits_available,
                    "errors": [
                        {"source": error.source, "reason": error.reason, "status_code": error.status_code}
                        for error in outcome.errors
                    ],
                }
            ),
        },
    )
    return len(accounts_by_connection) + 1


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
        canonical_rows = transaction.execute(
            """
            SELECT cm.canonical_slug, EXISTS (
                SELECT 1
                FROM artificial_analysis_model_metrics aa
                WHERE aa.canonical_model_id = cm.id
            ) AS has_aa_metrics
            FROM canonical_models cm
            """
        ).fetchall()
        canonical_slugs = {row["canonical_slug"] for row in canonical_rows}
        preferred_canonical_slugs = {row["canonical_slug"] for row in canonical_rows if row["has_aa_metrics"]}
        provider_catalog_ids = {row["provider_model_id"] for row in endpoints}
        matched = 0
        for endpoint in endpoints:
            result = match_model(
                endpoint["provider_model_id"],
                canonical_slugs=canonical_slugs,
                provider_catalog_ids=provider_catalog_ids,
                preferred_canonical_slugs=preferred_canonical_slugs,
            )
            status = "auto_use" if result.auto_use else "review_required"
            canonical_id = None
            if result.auto_use:
                slug = result.canonical_slug or canonical_slug(endpoint["provider_model_id"])
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
        return StageResult(
            status="validation_failed", reason="no_model_matches", details={"adapter": "model-matching", "effect": None}
        )
    return _effect_result("model-matching", changed=matched > 0)


def _detect_free_model_changes(transaction: Any, client: Any) -> FreeModelChanges:
    snapshots = transaction.execute(
        """
        SELECT raw_json
        FROM free_provider_registry_snapshots
        WHERE raw_json ? 'free_models'
        ORDER BY created_at DESC, id DESC
        LIMIT 2
        """
    ).fetchall()
    if len(snapshots) < 2:
        return FreeModelChanges(gained=set(), lost=set(), known=False)
    reachable = _reachable_providers(client)
    if reachable is None:
        return FreeModelChanges(gained=set(), lost=set(), known=False)
    current = _free_models_from_registry_snapshot(snapshots[0]["raw_json"])
    previous = _free_models_from_registry_snapshot(snapshots[1]["raw_json"])
    gained = {model for model in current - previous if model[0] in reachable}
    lost = {model for model in previous - current if model[0] in reachable}
    return FreeModelChanges(gained=gained, lost=lost)


def _free_models_from_registry_snapshot(raw_json: dict[str, Any]) -> set[tuple[str, str]]:
    free_models = raw_json.get("free_models", {})
    models = free_models.get("models", []) if isinstance(free_models, dict) else []
    return {
        (str(item["provider"]), str(item["modelId"]))
        for item in models
        if isinstance(item, dict) and item.get("provider") and item.get("modelId")
    }


def _reachable_providers(client: Any) -> set[str] | None:
    try:
        payload = client.get("/api/rate-limits")
    except Exception:
        return None
    connections = payload.get("connections") if isinstance(payload, dict) else None
    if not isinstance(connections, list):
        return None
    return {
        str(connection["provider"])
        for connection in connections
        if isinstance(connection, dict) and connection.get("provider") and connection.get("enabled", True)
    }


def _scan_catalogs(scanner: CatalogScanner, client: Any, omniroute_instance_id: str) -> object:
    return scan_live_omniroute_catalogs(scanner, client, omniroute_instance_id=omniroute_instance_id)
