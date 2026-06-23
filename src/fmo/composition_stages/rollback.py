from __future__ import annotations

from typing import Any

from fmo.idempotency import combo_models_idempotency_key as _combo_models_idempotency_key
from fmo.pipeline import PipelineContext, StageResult

from ._base import StageDependencies
from ._helpers import _effect_result


def _rollback_stage(dependencies: StageDependencies, context: PipelineContext) -> StageResult:
    if dependencies.omniroute_client is None:
        return StageResult(status="external_dependency_failed", reason="omniroute_client_required")
    with context.repository.database.transaction() as transaction:
        snapshots = _rollback_targets(transaction, context.config)
    if snapshots is None:
        return StageResult(status="validation_failed", reason="rollback_target_required")
    rollback_failed = False
    restored = []
    for snapshot in snapshots:
        combo_id = snapshot["omniroute_combo_id"]
        before = list(snapshot["state_json"].get("before", []))
        try:
            dependencies.omniroute_client.put(
                f"/api/combos/{combo_id}",
                {"models": before},
                idempotency_key=_combo_models_idempotency_key(combo_id, before),
            )
        except Exception:
            rollback_failed = True
            continue
        restored.append((snapshot, before))
    if rollback_failed:
        return StageResult(status="rollback_failed", reason="rollback_failed")
    with context.repository.database.transaction() as transaction:
        for snapshot, before in restored:
            context.repository.audit.record(
                transaction,
                run_id=context.run_id,
                entity_type="combo",
                entity_id=snapshot["omniroute_combo_id"],
                action="rollback_reverted",
                before_json={"applied": snapshot["state_json"].get("after", [])},
                after_json={"restored": before},
                reason_codes=["rollback_reverted"],
                source_refs=[
                    {
                        "source": "rollback-command",
                        "source_run_id": str(snapshot["run_id"]),
                        "role_id": snapshot["role_id"],
                    }
                ],
            )
    result = _effect_result("rollback", changed=bool(restored))
    return StageResult(
        status=result.status,
        idempotency_key=result.idempotency_key,
        changed=result.changed,
        details={**result.details, "restored": len(restored)},
    )


def _rollback_targets(transaction: Any, config: dict[str, Any]) -> list[Any] | None:
    run_id = config.get("run_id")
    endpoint = config.get("endpoint")
    role = config.get("role")
    if run_id:
        return transaction.execute(
            """
            SELECT DISTINCT ON (omniroute_combo_id)
                   id, run_id, role_id, omniroute_combo_id, state_json
            FROM combo_snapshots
            WHERE phase = 'applied'
              AND run_id = %(run_id)s
              AND left(omniroute_combo_id, 4) = 'fmo-'
            ORDER BY omniroute_combo_id, created_at DESC
            """,
            {"run_id": run_id},
        ).fetchall()
    combo_id = _rollback_combo_id(endpoint=endpoint, role=role)
    if combo_id is None:
        return None
    return transaction.execute(
        """
        SELECT DISTINCT ON (omniroute_combo_id)
               id, run_id, role_id, omniroute_combo_id, state_json
        FROM combo_snapshots
        WHERE phase = 'applied'
          AND omniroute_combo_id = %(combo_id)s
        ORDER BY omniroute_combo_id, created_at DESC
        """,
        {"combo_id": combo_id},
    ).fetchall()


def _rollback_combo_id(*, endpoint: str | None, role: str | None) -> str | None:
    if role:
        return role if role.startswith("fmo-") else f"fmo-{role}"
    if endpoint:
        return endpoint if endpoint.startswith("fmo-") else f"fmo-{endpoint}"
    return None
