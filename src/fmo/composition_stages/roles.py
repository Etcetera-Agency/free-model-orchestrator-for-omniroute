from __future__ import annotations

from typing import Any

from fmo.pipeline import PipelineContext, StageResult

from ._base import StageDependencies
from ._helpers import _effect_result


def _role_lifecycle_stage(_dependencies: StageDependencies, context: PipelineContext) -> StageResult:
    with context.repository.database.transaction() as transaction:
        desired = {
            row["role_id"]
            for row in transaction.execute("SELECT DISTINCT role_id FROM role_consumers WHERE active = true").fetchall()
        }
        roles = transaction.execute("SELECT id, role_lifecycle_status FROM roles").fetchall()
        changed = 0
        for role in roles:
            if role["id"] in desired and role["role_lifecycle_status"] in {"retiring", "retired_pending_delete"}:
                transaction.execute(
                    """
                    UPDATE roles
                    SET role_lifecycle_status = 'active',
                        missing_since = NULL
                    WHERE id = %(role_id)s
                    """,
                    {"role_id": role["id"]},
                )
                changed += 1
            elif role["id"] not in desired and role["role_lifecycle_status"] in {"active", "bootstrap_pending"}:
                transaction.execute(
                    """
                    UPDATE roles
                    SET role_lifecycle_status = 'retiring',
                        missing_since = COALESCE(missing_since, now())
                    WHERE id = %(role_id)s
                    """,
                    {"role_id": role["id"]},
                )
                changed += 1
    return _effect_result("role-lifecycle", changed=changed > 0)


def _latest_role_diagnostic(transaction: Any, role_id: str) -> dict[str, Any] | None:
    row = transaction.execute(
        """
        SELECT r.id AS role_id,
               r.role_lifecycle_status,
               r.requirements,
               r.expected_load,
               forecast.protected_requests,
               forecast.demand_source
        FROM roles r
        LEFT JOIN LATERAL (
          SELECT protected_requests, demand_source
          FROM role_demand_forecasts
          WHERE role_id = r.id
          ORDER BY created_at DESC
          LIMIT 1
        ) forecast ON true
        WHERE r.id = %(role_id)s
        LIMIT 1
        """,
        {"role_id": role_id},
    ).fetchone()
    return dict(row) if row is not None else None
