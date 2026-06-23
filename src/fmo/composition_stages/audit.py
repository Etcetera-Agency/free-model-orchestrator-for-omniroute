from __future__ import annotations

from fmo.pipeline import PipelineContext, StageResult

from ._base import StageDependencies
from ._helpers import _effect_result
from .apply import _read_current_combos


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
