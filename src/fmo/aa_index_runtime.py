from __future__ import annotations

from typing import Any

from psycopg.types.json import Jsonb

from fmo.aa_migration import run_migration_agent
from fmo.composition_contracts import RuntimeCliResult
from fmo.config import StartupConfig
from fmo.llm_runtime import SharedInstructorRuntime
from fmo.persistence import Repository
from fmo.quota_manager import LiveQuota, QuotaFetchError, fetch_live_quota_snapshot


def select_llm_model(repository: Repository, config: StartupConfig, live_quota_client: Any | None = None) -> str | None:
    live_quotas = _fresh_live_quotas(live_quota_client)
    if live_quotas is None:
        return None
    if repository is not None:
        with repository.database.transaction() as transaction:
            rows = transaction.execute(
                """
                SELECT f.provider_model_id, p.omniroute_provider_id, pa.omniroute_connection_id
                FROM free_model_definitions f
                JOIN provider_accounts pa
                  ON pa.omniroute_connection_id = COALESCE(f.omniroute_pool_key, f.provider_id)
                JOIN providers p
                  ON p.id = pa.provider_id
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
                """
            ).fetchall()
        for row in rows:
            quota_key = _quota_key(row["omniroute_provider_id"], row["omniroute_connection_id"])
            if _live_quota_usable(live_quotas.get(quota_key)):
                return row["provider_model_id"]
    if config.llm_bootstrap_model_id and config.llm_bootstrap_confirmed_free:
        bootstrap_quota = live_quotas.get(config.llm_bootstrap_model_id)
        if _live_quota_usable(bootstrap_quota):
            return config.llm_bootstrap_model_id
    return None


def _fresh_live_quotas(client: Any | None) -> dict[str, LiveQuota] | None:
    if client is None:
        return None
    try:
        return fetch_live_quota_snapshot(client).quotas
    except (QuotaFetchError, AttributeError, NotImplementedError):
        return None
    except Exception:
        return None


def _quota_key(provider_id: object, connection_id: object) -> str:
    return f"{provider_id}:{connection_id}"


def _live_quota_usable(quota: LiveQuota | None) -> bool:
    if quota is None or quota.locked_out:
        return False
    if quota.percent_remaining is None or quota.percent_remaining <= 10:
        return False
    if quota.learned_request_limit is None or quota.learned_request_remaining is None:
        return False
    return quota.learned_request_limit > 0 and quota.learned_request_remaining > 0


def _run_aa_index_command(
    repository: Repository,
    llm_runtime: SharedInstructorRuntime,
    config: StartupConfig,
    command: str,
) -> RuntimeCliResult:
    if command == "status":
        return RuntimeCliResult(exit_code=0, changed=False, output="ok")
    if command in {"analyze", "proposal"}:
        return _run_aa_index_proposal(repository, llm_runtime, config)
    if command == "approve":
        return _update_latest_aa_migration(repository, from_status="proposed", to_status="approved", changed=True)
    if command == "reject":
        return _update_latest_aa_migration(repository, from_status="proposed", to_status="rejected", changed=True)
    if command == "rollout":
        return _rollout_latest_aa_migration(repository)
    if command == "rollback":
        return _rollback_latest_aa_migration(repository)
    return RuntimeCliResult(exit_code=3, changed=False, error_reason="unknown_aa_index_command")


def _run_aa_index_proposal(
    repository: Repository, llm_runtime: SharedInstructorRuntime, config: StartupConfig
) -> RuntimeCliResult:
    with repository.database.transaction() as transaction:
        latest = transaction.execute(
            """
            SELECT index_version
            FROM artificial_analysis_model_metrics
            ORDER BY fetched_at DESC
            LIMIT 1
            """
        ).fetchone()
    if latest is None:
        return RuntimeCliResult(exit_code=4, changed=False, error_reason="aa_unavailable")
    model = select_llm_model(repository, config)
    if model is None:
        return RuntimeCliResult(exit_code=4, changed=False, error_reason="migration_model_unavailable")
    proposal = run_migration_agent(llm_runtime, {"endpoint": model, "available": True})
    if proposal.get("status") in {"waiting_for_model", "advisory_unavailable"}:
        return RuntimeCliResult(exit_code=4, changed=False, error_reason=str(proposal.get("status")))
    with repository.database.transaction() as transaction:
        transaction.execute(
            """
            INSERT INTO artificial_analysis_index_migrations (
              new_index_version, change_type, status, baseline_snapshot_json,
              threshold_proposal_json, llm_proposal_json
            )
            VALUES (
              %(version)s, 'major', 'proposed', '{}'::jsonb,
              %(proposal)s, %(proposal)s
            )
            """,
            {"version": latest["index_version"], "proposal": Jsonb(proposal)},
        )
    return RuntimeCliResult(exit_code=0, changed=True)


def _update_latest_aa_migration(
    repository: Repository,
    *,
    from_status: str,
    to_status: str,
    changed: bool,
) -> RuntimeCliResult:
    with repository.database.transaction() as transaction:
        row = transaction.execute(
            """
            UPDATE artificial_analysis_index_migrations
            SET status = %(to_status)s,
                approved_at = CASE WHEN %(to_status)s = 'approved' THEN now() ELSE approved_at END,
                rolled_back_at = CASE WHEN %(to_status)s = 'rolled_back' THEN now() ELSE rolled_back_at END,
                updated_at = now()
            WHERE id = (
              SELECT id
              FROM artificial_analysis_index_migrations
              WHERE status = %(from_status)s
              ORDER BY created_at DESC
              LIMIT 1
            )
            RETURNING id
            """,
            {"from_status": from_status, "to_status": to_status},
        ).fetchone()
    if row is None:
        return RuntimeCliResult(exit_code=3, changed=False, error_reason="migration_not_found")
    return RuntimeCliResult(exit_code=0, changed=changed)


def _rollout_latest_aa_migration(repository: Repository) -> RuntimeCliResult:
    with repository.database.transaction() as transaction:
        row = transaction.execute(
            """
            SELECT id, new_index_version, threshold_proposal_json
            FROM artificial_analysis_index_migrations
            WHERE status = 'approved'
            ORDER BY created_at DESC
            LIMIT 1
            """
        ).fetchone()
        if row is None:
            return RuntimeCliResult(exit_code=3, changed=False, error_reason="migration_not_found")
        for role_id, policy in (row["threshold_proposal_json"].get("roles") or {}).items():
            transaction.execute(
                """
                UPDATE artificial_analysis_threshold_versions
                SET is_active = false
                WHERE role_id = %(role_id)s
                """,
                {"role_id": role_id},
            )
            transaction.execute(
                """
                INSERT INTO artificial_analysis_threshold_versions (
                  role_id, metric, threshold_value, index_version, migration_id, is_active
                )
                VALUES (
                  %(role_id)s, %(metric)s, %(threshold)s, %(version)s, %(migration_id)s, true
                )
                """,
                {
                    "role_id": role_id,
                    "metric": policy["metric"],
                    "threshold": policy.get("threshold", policy.get("threshold_value", 0)),
                    "version": row["new_index_version"],
                    "migration_id": row["id"],
                },
            )
        transaction.execute(
            """
            UPDATE artificial_analysis_index_migrations
            SET status = 'rolled_out', rolled_out_at = now(), updated_at = now()
            WHERE id = %(id)s
            """,
            {"id": row["id"]},
        )
    return RuntimeCliResult(exit_code=0, changed=True)


def _rollback_latest_aa_migration(repository: Repository) -> RuntimeCliResult:
    with repository.database.transaction() as transaction:
        row = transaction.execute(
            """
            UPDATE artificial_analysis_index_migrations
            SET status = 'rolled_back', rolled_back_at = now(), updated_at = now()
            WHERE id = (
              SELECT id
              FROM artificial_analysis_index_migrations
              WHERE status = 'rolled_out'
              ORDER BY created_at DESC
              LIMIT 1
            )
            RETURNING id
            """
        ).fetchone()
        if row is None:
            return RuntimeCliResult(exit_code=3, changed=False, error_reason="migration_not_found")
        transaction.execute(
            """
            UPDATE artificial_analysis_threshold_versions
            SET is_active = false
            WHERE migration_id = %(migration_id)s
            """,
            {"migration_id": row["id"]},
        )
    return RuntimeCliResult(exit_code=0, changed=True)
