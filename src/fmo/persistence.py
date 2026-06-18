from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


Record = dict[str, Any]


class Database:
    def __init__(self, database_url: str):
        self.database_url = database_url

    @contextmanager
    def transaction(self) -> Iterator[psycopg.Connection[Record]]:
        with psycopg.connect(self.database_url, row_factory=dict_row) as connection:
            try:
                yield connection
            except Exception:
                connection.rollback()
                raise
            else:
                connection.commit()


@dataclass(frozen=True)
class Repository:
    database: Database

    def __post_init__(self) -> None:
        object.__setattr__(self, "runs", RunRepository())
        object.__setattr__(self, "providers", ProviderRepository())
        object.__setattr__(self, "provider_accounts", ProviderAccountRepository())
        object.__setattr__(self, "canonical_models", CanonicalModelRepository())
        object.__setattr__(self, "provider_endpoints", ProviderEndpointRepository())
        object.__setattr__(self, "snapshots", SnapshotRepository())
        object.__setattr__(self, "quota_rules", QuotaRuleRepository())
        object.__setattr__(self, "probes", ProbeRepository())
        object.__setattr__(self, "roles", RoleRepository())
        object.__setattr__(self, "scores", ScoreRepository())
        object.__setattr__(self, "allocation_plans", AllocationPlanRepository())
        object.__setattr__(self, "combo_snapshots", ComboSnapshotRepository())
        object.__setattr__(self, "audit", AuditRepository())


class RunRepository:
    def create(
        self,
        connection: psycopg.Connection[Record],
        *,
        run_type: str,
        trigger: str,
        status: str,
        code_version: str,
        config_hash: str,
        omniroute_version: str | None = None,
        error_json: dict[str, Any] | None = None,
    ) -> Record:
        return _one(
            connection,
            """
            INSERT INTO sync_runs (
              run_type, trigger, status, code_version, config_hash,
              omniroute_version, error_json
            )
            VALUES (
              %(run_type)s, %(trigger)s, %(status)s, %(code_version)s,
              %(config_hash)s, %(omniroute_version)s, %(error_json)s
            )
            RETURNING *
            """,
            {
                "run_type": run_type,
                "trigger": trigger,
                "status": status,
                "code_version": code_version,
                "config_hash": config_hash,
                "omniroute_version": omniroute_version,
                "error_json": _jsonb(error_json),
            },
        )

    def get(self, connection: psycopg.Connection[Record], run_id: Any) -> Record | None:
        return _optional(connection, "SELECT * FROM sync_runs WHERE id = %(id)s", {"id": run_id})

    def list(self, connection: psycopg.Connection[Record]) -> list[Record]:
        return _many(connection, "SELECT * FROM sync_runs ORDER BY started_at, id")

    def finish(
        self,
        connection: psycopg.Connection[Record],
        run_id: Any,
        *,
        status: str,
        stages: list[dict[str, Any]],
    ) -> Record:
        return _one(
            connection,
            """
            UPDATE sync_runs
            SET status = %(status)s,
                finished_at = now(),
                error_json = %(error_json)s
            WHERE id = %(id)s
            RETURNING *
            """,
            {
                "id": run_id,
                "status": status,
                "error_json": _jsonb({"stages": stages}),
            },
        )

    def last_successful_stage(
        self,
        connection: psycopg.Connection[Record],
        *,
        stage_name: str,
        idempotency_key: str,
    ) -> dict[str, Any] | None:
        for run in reversed(self.list(connection)):
            payload = run.get("error_json")
            if not isinstance(payload, dict):
                continue
            for stage in payload.get("stages", []):
                if not isinstance(stage, dict):
                    continue
                if (
                    stage.get("name") == stage_name
                    and stage.get("idempotency_key") == idempotency_key
                    and stage.get("status") == "success"
                    and not stage.get("skipped")
                ):
                    return stage
        return None


class ProviderRepository:
    def upsert(
        self,
        connection: psycopg.Connection[Record],
        *,
        omniroute_instance_id: str,
        omniroute_provider_id: str,
        provider_type: str,
        display_name: str | None = None,
        enabled: bool = True,
        provider_group: str | None = None,
        raw_config_hash: str | None = None,
    ) -> Record:
        return _one(
            connection,
            """
            INSERT INTO providers (
              omniroute_instance_id, omniroute_provider_id, provider_type,
              display_name, enabled, provider_group, raw_config_hash
            )
            VALUES (
              %(omniroute_instance_id)s, %(omniroute_provider_id)s,
              %(provider_type)s, %(display_name)s, %(enabled)s,
              %(provider_group)s, %(raw_config_hash)s
            )
            ON CONFLICT (omniroute_instance_id, omniroute_provider_id)
            DO UPDATE SET
              provider_type = EXCLUDED.provider_type,
              display_name = EXCLUDED.display_name,
              enabled = EXCLUDED.enabled,
              provider_group = EXCLUDED.provider_group,
              raw_config_hash = EXCLUDED.raw_config_hash,
              last_seen_at = now()
            RETURNING *
            """,
            {
                "omniroute_instance_id": omniroute_instance_id,
                "omniroute_provider_id": omniroute_provider_id,
                "provider_type": provider_type,
                "display_name": display_name,
                "enabled": enabled,
                "provider_group": provider_group,
                "raw_config_hash": raw_config_hash,
            },
        )


class ProviderAccountRepository:
    def upsert(
        self,
        connection: psycopg.Connection[Record],
        *,
        provider_id: Any,
        omniroute_connection_id: str | None = None,
        external_account_ref: str | None = None,
        metadata: dict[str, Any] | None = None,
        enabled: bool = True,
    ) -> Record:
        existing = _optional(
            connection,
            """
            SELECT * FROM provider_accounts
            WHERE provider_id = %(provider_id)s
              AND omniroute_connection_id IS NOT DISTINCT FROM %(omniroute_connection_id)s
            ORDER BY first_seen_at
            LIMIT 1
            """,
            {"provider_id": provider_id, "omniroute_connection_id": omniroute_connection_id},
        )
        if existing:
            return _one(
                connection,
                """
                UPDATE provider_accounts
                SET external_account_ref = %(external_account_ref)s,
                    metadata = %(metadata)s,
                    enabled = %(enabled)s,
                    last_seen_at = now()
                WHERE id = %(id)s
                RETURNING *
                """,
                {
                    "id": existing["id"],
                    "external_account_ref": external_account_ref,
                    "metadata": _jsonb(metadata or {}),
                    "enabled": enabled,
                },
            )
        return _one(
            connection,
            """
            INSERT INTO provider_accounts (
              provider_id, omniroute_connection_id, external_account_ref,
              metadata, enabled
            )
            VALUES (
              %(provider_id)s, %(omniroute_connection_id)s,
              %(external_account_ref)s, %(metadata)s, %(enabled)s
            )
            RETURNING *
            """,
            {
                "provider_id": provider_id,
                "omniroute_connection_id": omniroute_connection_id,
                "external_account_ref": external_account_ref,
                "metadata": _jsonb(metadata or {}),
                "enabled": enabled,
            },
        )


class CanonicalModelRepository:
    def upsert(
        self,
        connection: psycopg.Connection[Record],
        *,
        canonical_slug: str,
        lab: str | None = None,
        family: str | None = None,
        version: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Record:
        return _one(
            connection,
            """
            INSERT INTO canonical_models (canonical_slug, lab, family, version, metadata)
            VALUES (%(canonical_slug)s, %(lab)s, %(family)s, %(version)s, %(metadata)s)
            ON CONFLICT (canonical_slug)
            DO UPDATE SET
              lab = EXCLUDED.lab,
              family = EXCLUDED.family,
              version = EXCLUDED.version,
              metadata = EXCLUDED.metadata,
              updated_at = now()
            RETURNING *
            """,
            {
                "canonical_slug": canonical_slug,
                "lab": lab,
                "family": family,
                "version": version,
                "metadata": _jsonb(metadata or {}),
            },
        )


class ProviderEndpointRepository:
    def upsert(
        self,
        connection: psycopg.Connection[Record],
        *,
        provider_account_id: Any,
        provider_model_id: str,
        model_type: str = "chat",
        canonical_model_id: Any | None = None,
        lifecycle_status: str,
        access_status: str,
        probe_status: str = "not_run",
        capabilities: dict[str, Any] | None = None,
        metadata_hash: str | None = None,
    ) -> Record:
        return _one(
            connection,
            """
            INSERT INTO provider_endpoints (
              provider_account_id, provider_model_id, model_type,
              canonical_model_id, lifecycle_status, access_status,
              probe_status, capabilities, metadata_hash
            )
            VALUES (
              %(provider_account_id)s, %(provider_model_id)s, %(model_type)s,
              %(canonical_model_id)s, %(lifecycle_status)s, %(access_status)s,
              %(probe_status)s, %(capabilities)s, %(metadata_hash)s
            )
            ON CONFLICT (provider_account_id, provider_model_id, model_type)
            DO UPDATE SET
              canonical_model_id = EXCLUDED.canonical_model_id,
              lifecycle_status = EXCLUDED.lifecycle_status,
              access_status = EXCLUDED.access_status,
              probe_status = EXCLUDED.probe_status,
              capabilities = EXCLUDED.capabilities,
              metadata_hash = EXCLUDED.metadata_hash,
              last_seen_at = now()
            RETURNING *
            """,
            {
                "provider_account_id": provider_account_id,
                "provider_model_id": provider_model_id,
                "model_type": model_type,
                "canonical_model_id": canonical_model_id,
                "lifecycle_status": lifecycle_status,
                "access_status": access_status,
                "probe_status": probe_status,
                "capabilities": _jsonb(capabilities or {}),
                "metadata_hash": metadata_hash,
            },
        )

    def get(self, connection: psycopg.Connection[Record], endpoint_id: Any) -> Record | None:
        return _optional(connection, "SELECT * FROM provider_endpoints WHERE id = %(id)s", {"id": endpoint_id})


class SnapshotRepository:
    def store_quota_source(
        self,
        connection: psycopg.Connection[Record],
        *,
        source_url: str,
        source_type: str,
        payload: dict[str, Any],
        title: str | None = None,
        http_status: int | None = None,
    ) -> Record:
        normalized_content = _canonical_json(payload)
        content_hash = _content_hash(normalized_content)
        existing = _optional(
            connection,
            """
            SELECT * FROM quota_source_snapshots
            WHERE source_url = %(source_url)s AND content_hash = %(content_hash)s
            """,
            {"source_url": source_url, "content_hash": content_hash},
        )
        if existing:
            return existing
        return _one(
            connection,
            """
            INSERT INTO quota_source_snapshots (
              source_url, source_type, title, http_status, content_hash,
              normalized_content
            )
            VALUES (
              %(source_url)s, %(source_type)s, %(title)s, %(http_status)s,
              %(content_hash)s, %(normalized_content)s
            )
            RETURNING *
            """,
            {
                "source_url": source_url,
                "source_type": source_type,
                "title": title,
                "http_status": http_status,
                "content_hash": content_hash,
                "normalized_content": normalized_content,
            },
        )

    def count_by_hash(self, connection: psycopg.Connection[Record], content_hash: str) -> int:
        row = _one(
            connection,
            "SELECT count(*) AS total FROM quota_source_snapshots WHERE content_hash = %(content_hash)s",
            {"content_hash": content_hash},
        )
        return int(row["total"])


class QuotaRuleRepository:
    def upsert(
        self,
        connection: psycopg.Connection[Record],
        *,
        provider_id: Any,
        provider_account_id: Any | None,
        source_snapshot_id: Any | None,
        model_pattern: str,
        access_type: str,
        limits: dict[str, Any],
        reset_policy: dict[str, Any],
        hard_stop_capable: bool,
        confidence: float,
        status: str,
        rule_hash: str,
    ) -> Record:
        existing = _optional(connection, "SELECT * FROM quota_rules WHERE rule_hash = %(rule_hash)s", {"rule_hash": rule_hash})
        if existing:
            return existing
        return _one(
            connection,
            """
            INSERT INTO quota_rules (
              provider_id, provider_account_id, source_snapshot_id, model_pattern,
              access_type, limits, reset_policy, hard_stop_capable, confidence,
              status, rule_hash
            )
            VALUES (
              %(provider_id)s, %(provider_account_id)s, %(source_snapshot_id)s,
              %(model_pattern)s, %(access_type)s, %(limits)s, %(reset_policy)s,
              %(hard_stop_capable)s, %(confidence)s, %(status)s, %(rule_hash)s
            )
            RETURNING *
            """,
            {
                "provider_id": provider_id,
                "provider_account_id": provider_account_id,
                "source_snapshot_id": source_snapshot_id,
                "model_pattern": model_pattern,
                "access_type": access_type,
                "limits": _jsonb(limits),
                "reset_policy": _jsonb(reset_policy),
                "hard_stop_capable": hard_stop_capable,
                "confidence": Decimal(str(confidence)),
                "status": status,
                "rule_hash": rule_hash,
            },
        )

    def get(self, connection: psycopg.Connection[Record], rule_id: Any) -> Record | None:
        return _optional(connection, "SELECT * FROM quota_rules WHERE id = %(id)s", {"id": rule_id})


class ProbeRepository:
    def record(
        self,
        connection: psycopg.Connection[Record],
        *,
        endpoint_id: Any,
        suite_version: str,
        probe_type: str,
        request_hash: str,
        passed: bool,
        started_at: Any,
        finished_at: Any,
        http_status: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> Record:
        existing = _optional(
            connection,
            """
            SELECT * FROM endpoint_probes
            WHERE endpoint_id = %(endpoint_id)s AND request_hash = %(request_hash)s
            ORDER BY started_at
            LIMIT 1
            """,
            {"endpoint_id": endpoint_id, "request_hash": request_hash},
        )
        if existing:
            return existing
        return _one(
            connection,
            """
            INSERT INTO endpoint_probes (
              endpoint_id, suite_version, probe_type, request_hash, passed,
              http_status, details, started_at, finished_at
            )
            VALUES (
              %(endpoint_id)s, %(suite_version)s, %(probe_type)s,
              %(request_hash)s, %(passed)s, %(http_status)s, %(details)s,
              %(started_at)s, %(finished_at)s
            )
            RETURNING *
            """,
            {
                "endpoint_id": endpoint_id,
                "suite_version": suite_version,
                "probe_type": probe_type,
                "request_hash": request_hash,
                "passed": passed,
                "http_status": http_status,
                "details": _jsonb(details or {}),
                "started_at": started_at,
                "finished_at": finished_at,
            },
        )

    def get(self, connection: psycopg.Connection[Record], probe_id: Any) -> Record | None:
        return _optional(connection, "SELECT * FROM endpoint_probes WHERE id = %(id)s", {"id": probe_id})

    def count_by_request_hash(self, connection: psycopg.Connection[Record], request_hash: str) -> int:
        row = _one(
            connection,
            "SELECT count(*) AS total FROM endpoint_probes WHERE request_hash = %(request_hash)s",
            {"request_hash": request_hash},
        )
        return int(row["total"])


class RoleRepository:
    def upsert(
        self,
        connection: psycopg.Connection[Record],
        *,
        role_id: str,
        requirements: dict[str, Any],
        expected_load: dict[str, Any],
        criticality: int,
    ) -> Record:
        return _one(
            connection,
            """
            INSERT INTO roles (id, requirements, expected_load, criticality)
            VALUES (%(role_id)s, %(requirements)s, %(expected_load)s, %(criticality)s)
            ON CONFLICT (id)
            DO UPDATE SET
              requirements = EXCLUDED.requirements,
              expected_load = EXCLUDED.expected_load,
              criticality = EXCLUDED.criticality
            RETURNING *
            """,
            {
                "role_id": role_id,
                "requirements": _jsonb(requirements),
                "expected_load": _jsonb(expected_load),
                "criticality": criticality,
            },
        )


class ScoreRepository:
    def upsert(
        self,
        connection: psycopg.Connection[Record],
        *,
        role_id: str,
        endpoint_id: Any,
        score_version: str,
        total_score: float,
        component_scores: dict[str, Any],
        eligibility: bool,
        input_state_hash: str,
        rejection_reasons: list[str] | None = None,
    ) -> Record:
        existing = _optional(
            connection,
            """
            SELECT * FROM role_scores
            WHERE role_id = %(role_id)s
              AND endpoint_id = %(endpoint_id)s
              AND score_version = %(score_version)s
              AND input_state_hash = %(input_state_hash)s
            ORDER BY calculated_at
            LIMIT 1
            """,
            {
                "role_id": role_id,
                "endpoint_id": endpoint_id,
                "score_version": score_version,
                "input_state_hash": input_state_hash,
            },
        )
        if existing:
            return existing
        return _one(
            connection,
            """
            INSERT INTO role_scores (
              role_id, endpoint_id, score_version, total_score, component_scores,
              eligibility, rejection_reasons, input_state_hash
            )
            VALUES (
              %(role_id)s, %(endpoint_id)s, %(score_version)s, %(total_score)s,
              %(component_scores)s, %(eligibility)s, %(rejection_reasons)s,
              %(input_state_hash)s
            )
            RETURNING *
            """,
            {
                "role_id": role_id,
                "endpoint_id": endpoint_id,
                "score_version": score_version,
                "total_score": Decimal(str(total_score)),
                "component_scores": _jsonb(component_scores),
                "eligibility": eligibility,
                "rejection_reasons": _jsonb(rejection_reasons),
                "input_state_hash": input_state_hash,
            },
        )

    def get(self, connection: psycopg.Connection[Record], score_id: Any) -> Record | None:
        return _optional(connection, "SELECT * FROM role_scores WHERE id = %(id)s", {"id": score_id})


class AllocationPlanRepository:
    def upsert(
        self,
        connection: psycopg.Connection[Record],
        *,
        role_id: str,
        status: str,
        targets: list[dict[str, Any]],
        constraint_report: dict[str, Any],
        input_state_hash: str,
    ) -> Record:
        existing = _optional(
            connection,
            """
            SELECT * FROM allocation_plans
            WHERE role_id = %(role_id)s AND input_state_hash = %(input_state_hash)s
            ORDER BY created_at
            LIMIT 1
            """,
            {"role_id": role_id, "input_state_hash": input_state_hash},
        )
        if existing:
            return existing
        return _one(
            connection,
            """
            INSERT INTO allocation_plans (
              role_id, status, targets, constraint_report, input_state_hash
            )
            VALUES (
              %(role_id)s, %(status)s, %(targets)s, %(constraint_report)s,
              %(input_state_hash)s
            )
            RETURNING *
            """,
            {
                "role_id": role_id,
                "status": status,
                "targets": _jsonb(targets),
                "constraint_report": _jsonb(constraint_report),
                "input_state_hash": input_state_hash,
            },
        )

    def get(self, connection: psycopg.Connection[Record], plan_id: Any) -> Record | None:
        return _optional(connection, "SELECT * FROM allocation_plans WHERE id = %(id)s", {"id": plan_id})


class ComboSnapshotRepository:
    def upsert(
        self,
        connection: psycopg.Connection[Record],
        *,
        role_id: str,
        state_hash: str,
        state_json: dict[str, Any],
        phase: str,
        omniroute_combo_id: str | None = None,
        run_id: Any | None = None,
    ) -> Record:
        existing = _optional(
            connection,
            """
            SELECT * FROM combo_snapshots
            WHERE role_id = %(role_id)s AND state_hash = %(state_hash)s AND phase = %(phase)s
            ORDER BY created_at
            LIMIT 1
            """,
            {"role_id": role_id, "state_hash": state_hash, "phase": phase},
        )
        if existing:
            return existing
        return _one(
            connection,
            """
            INSERT INTO combo_snapshots (
              role_id, omniroute_combo_id, state_hash, state_json, phase, run_id
            )
            VALUES (
              %(role_id)s, %(omniroute_combo_id)s, %(state_hash)s,
              %(state_json)s, %(phase)s, %(run_id)s
            )
            RETURNING *
            """,
            {
                "role_id": role_id,
                "omniroute_combo_id": omniroute_combo_id,
                "state_hash": state_hash,
                "state_json": _jsonb(state_json),
                "phase": phase,
                "run_id": run_id,
            },
        )

    def get(self, connection: psycopg.Connection[Record], snapshot_id: Any) -> Record | None:
        return _optional(connection, "SELECT * FROM combo_snapshots WHERE id = %(id)s", {"id": snapshot_id})


class AuditRepository:
    def record(
        self,
        connection: psycopg.Connection[Record],
        *,
        entity_type: str,
        entity_id: str,
        action: str,
        run_id: Any | None = None,
        before_json: dict[str, Any] | None = None,
        after_json: dict[str, Any] | None = None,
        reason_codes: list[str] | None = None,
        source_refs: list[dict[str, Any]] | None = None,
    ) -> Record:
        return _one(
            connection,
            """
            INSERT INTO change_log (
              run_id, entity_type, entity_id, action, before_json, after_json,
              reason_codes, source_refs
            )
            VALUES (
              %(run_id)s, %(entity_type)s, %(entity_id)s, %(action)s,
              %(before_json)s, %(after_json)s, %(reason_codes)s, %(source_refs)s
            )
            RETURNING *
            """,
            {
                "run_id": run_id,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "action": action,
                "before_json": _jsonb(before_json),
                "after_json": _jsonb(after_json),
                "reason_codes": _jsonb(reason_codes or []),
                "source_refs": _jsonb(source_refs or []),
            },
        )

    def get(self, connection: psycopg.Connection[Record], audit_id: Any) -> Record | None:
        return _optional(connection, "SELECT * FROM change_log WHERE id = %(id)s", {"id": audit_id})


def _one(connection: psycopg.Connection[Record], sql: str, params: dict[str, Any] | None = None) -> Record:
    row = connection.execute(sql, params or {}).fetchone()
    if row is None:
        raise LookupError("expected one row")
    return dict(row)


def _optional(connection: psycopg.Connection[Record], sql: str, params: dict[str, Any] | None = None) -> Record | None:
    row = connection.execute(sql, params or {}).fetchone()
    return dict(row) if row is not None else None


def _many(connection: psycopg.Connection[Record], sql: str, params: dict[str, Any] | None = None) -> list[Record]:
    return [dict(row) for row in connection.execute(sql, params or {}).fetchall()]


def _jsonb(value: Any) -> Jsonb | None:
    if value is None:
        return None
    return Jsonb(value)


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
