from __future__ import annotations

from typing import Any

from psycopg.types.json import Jsonb

from fmo.aa_migration import migration_validation_errors, run_migration_agent
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
    repository: Repository, llm_runtime: SharedInstructorRuntime, _config: StartupConfig
) -> RuntimeCliResult:
    context = build_migration_context(repository)
    if context is None:
        return RuntimeCliResult(exit_code=4, changed=False, error_reason="aa_unavailable")
    proposal, attempt_report = _valid_migration_proposal(llm_runtime, context)
    if proposal is None:
        return RuntimeCliResult(exit_code=4, changed=False, error_reason=attempt_report["status"])
    with repository.database.transaction() as transaction:
        transaction.execute(
            """
            INSERT INTO artificial_analysis_index_migrations (
              new_index_version, change_type, status, baseline_snapshot_json,
              threshold_proposal_json, llm_proposal_json
            )
            VALUES (
              %(version)s, 'major', 'proposed', %(baseline)s,
              %(proposal)s, %(attempt_report)s
            )
            """,
            {
                "version": context["new_index_version"],
                "baseline": Jsonb(context),
                "proposal": Jsonb(proposal),
                "attempt_report": Jsonb(attempt_report),
            },
        )
    return RuntimeCliResult(exit_code=0, changed=True)


def _valid_migration_proposal(
    llm_runtime: SharedInstructorRuntime,
    context: dict[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    errors: list[str] = []
    attempts = []
    for attempt in range(1, 4):
        proposal = run_migration_agent(llm_runtime, context, repair_errors=errors)
        attempts.append({"attempt": attempt, "proposal": proposal, "repair_errors": list(errors)})
        if proposal.get("status") in {"waiting_for_model", "advisory_unavailable"}:
            return None, {"status": str(proposal.get("status")), "attempts": attempts}
        errors = migration_validation_errors(
            proposal,
            new_version=str(context["new_index_version"]),
            role_capacity=context["role_capacity"],
        )
        attempts[-1]["validation_errors"] = list(errors)
        if not errors:
            return proposal, {"status": "valid", "attempts": attempts}
    return None, {"status": "migration_needs_manual_review", "attempts": attempts}


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
            SELECT id, new_index_version, threshold_proposal_json, baseline_snapshot_json
            FROM artificial_analysis_index_migrations
            WHERE status = 'approved'
            ORDER BY created_at DESC
            LIMIT 1
            """
        ).fetchone()
        if row is None:
            return RuntimeCliResult(exit_code=3, changed=False, error_reason="migration_not_found")
        # AICODE-NOTE: Rollout validates against current repository state, not
        # only the approved proposal, so quota/health/capability drift blocks.
        current_context = build_migration_context(repository)
        proposal = row["threshold_proposal_json"] or {}
        validation_context = current_context or row["baseline_snapshot_json"] or {}
        errors = migration_validation_errors(
            proposal,
            new_version=row["new_index_version"],
            role_capacity=validation_context.get("role_capacity", {}),
        )
        if errors:
            transaction.execute(
                """
                UPDATE artificial_analysis_index_migrations
                SET validation_report_json = %(report)s,
                    updated_at = now()
                WHERE id = %(id)s
                """,
                {"id": row["id"], "report": Jsonb({"status": "blocked", "errors": errors})},
            )
            return RuntimeCliResult(exit_code=4, changed=False, error_reason="migration_validation_failed")
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
                    "threshold": policy["threshold_value"],
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


def build_migration_context(repository: Repository) -> dict[str, Any] | None:
    # AICODE-NOTE: Baseline snapshot builder feeds both prompt context and
    # rollout audit; keep it deterministic and free of provider secrets.
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
            return None
        new_version = latest["index_version"]
        active_versions = transaction.execute(
            """
            SELECT role_id, metric, threshold_value, index_version
            FROM artificial_analysis_threshold_versions
            WHERE is_active = true
            ORDER BY role_id
            """
        ).fetchall()
        old_version = active_versions[0]["index_version"] if active_versions else None
        roles = transaction.execute("SELECT id, requirements, criticality FROM roles ORDER BY id").fetchall()
        combos = transaction.execute(
            """
            SELECT DISTINCT ON (role_id) role_id, omniroute_combo_id, state_json
            FROM combo_snapshots
            WHERE omniroute_combo_id LIKE 'fmo-%'
            ORDER BY role_id, created_at DESC
            """
        ).fetchall()
        role_capacity = _role_capacity(transaction, new_version)
        return {
            "old_index_version": old_version,
            "new_index_version": new_version,
            "old_distribution": _metric_distribution(transaction, old_version),
            "new_distribution": _metric_distribution(transaction, new_version),
            "roles": [
                {
                    "role_id": role["id"],
                    "requirements": role["requirements"] or {},
                    "criticality": int(role["criticality"]),
                    "active_threshold": next(
                        (dict(item) for item in active_versions if item["role_id"] == role["id"]),
                        None,
                    ),
                    "current_combo": next(
                        (combo["state_json"] for combo in combos if combo["role_id"] == role["id"]),
                        None,
                    ),
                }
                for role in roles
            ],
            "capacity_summary": role_capacity,
            "role_capacity": role_capacity,
            "percentile_mapping": _percentile_mapping(active_versions, role_capacity),
        }


def _metric_distribution(transaction: Any, version: str | None) -> dict[str, Any]:
    if version is None:
        return {}
    rows = transaction.execute(
        """
        SELECT
          min(intelligence_index) AS intelligence_min,
          max(intelligence_index) AS intelligence_max,
          min(coding_index) AS coding_min,
          max(coding_index) AS coding_max,
          min(agentic_index) AS agentic_min,
          max(agentic_index) AS agentic_max,
          count(*) AS total
        FROM artificial_analysis_model_metrics
        WHERE index_version = %(version)s
        """,
        {"version": version},
    ).fetchone()
    return dict(rows or {})


def _role_capacity(transaction: Any, version: str) -> dict[str, dict[str, Any]]:
    roles = transaction.execute("SELECT id, requirements FROM roles ORDER BY id").fetchall()
    result: dict[str, dict[str, Any]] = {}
    for role in roles:
        rows = transaction.execute(
            """
            SELECT pe.id, pe.capabilities, pe.effective_context_window,
                   COALESCE(pa.quota_pool_id, pe.provider_account_id) AS pool_id,
                   p.provider_group, p.omniroute_provider_id,
                   eas.status AS access_status, eas.effective_remaining, eas.evidence,
                   COALESCE(health.status, 'active') AS health_status,
                   aa.intelligence_index, aa.coding_index, aa.agentic_index
            FROM provider_endpoints pe
            JOIN provider_accounts pa ON pa.id = pe.provider_account_id
            JOIN providers p ON p.id = pa.provider_id
            JOIN endpoint_access_states eas ON eas.endpoint_id = pe.id
            JOIN artificial_analysis_model_metrics aa ON aa.canonical_model_id = pe.canonical_model_id
            LEFT JOIN LATERAL (
              SELECT status
              FROM endpoint_health_observations h
              WHERE h.endpoint_id = pe.id
              ORDER BY observed_at DESC
              LIMIT 1
            ) health ON true
            WHERE aa.index_version = %(version)s
              AND eas.status = 'confirmed'
            """,
            {"version": version},
        ).fetchall()
        requirements = role["requirements"] or {}
        minimum_context = int(requirements.get("minimum_context_window") or 0)
        required_capabilities = set(requirements.get("capabilities", []))
        eligible = [
            row
            for row in rows
            if _endpoint_matches_role(row, minimum_context=minimum_context, required_capabilities=required_capabilities)
        ]
        result[role["id"]] = {
            "eligible": len(eligible),
            "minimum": 1,
            "minimum_independent_pools": 1,
            "minimum_provider_groups": 1,
            "independent_quota_pools": len({str(row["pool_id"]) for row in eligible}),
            "provider_groups": len({str(row["provider_group"] or row["omniroute_provider_id"]) for row in eligible}),
            "quota_ok": all(_effective_remaining_positive(row["effective_remaining"]) for row in eligible),
            "quality_ok": bool(eligible),
            "context_ok": all(int(row["effective_context_window"] or 0) >= minimum_context for row in eligible),
            "capabilities_ok": True,
            "free_confirmed": all(row["access_status"] == "confirmed" for row in eligible),
            "healthy": all(row["health_status"] == "active" for row in eligible),
            "live_quota_ok": all(_live_evidence_ok(row["evidence"]) for row in eligible),
            "min_threshold": 0,
            "max_threshold": 100,
        }
    return result


def _endpoint_matches_role(row: Any, *, minimum_context: int, required_capabilities: set[str]) -> bool:
    capabilities = row["capabilities"] if isinstance(row["capabilities"], dict) else {}
    inputs = set(capabilities.get("input", []))
    return int(row["effective_context_window"] or 0) >= minimum_context and required_capabilities.issubset(inputs)


def _effective_remaining_positive(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    return any(float(amount or 0) > 0 for amount in value.values())


def _live_evidence_ok(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    return value.get("remaining_source") == "live_observed" and value.get("locked_out") is not True


def _percentile_mapping(active_versions: list[Any], role_capacity: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        row["role_id"]: {
            "old_percentile": 0.5,
            "new_same_percentile_threshold": min(
                max(float(row["threshold_value"]), role_capacity.get(row["role_id"], {}).get("min_threshold", 0)),
                role_capacity.get(row["role_id"], {}).get("max_threshold", 100),
            ),
        }
        for row in active_versions
    }


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
