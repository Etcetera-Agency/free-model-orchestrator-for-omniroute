from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Any

from fmo.applier import ComboApplier
from fmo.apply_guard import ApplyPreconditions, check_apply_preconditions
from fmo.config import DEFAULT_APPLY_MIN_PERCENT_REMAINING, DEFAULT_APPLY_MIN_SAFETY_BUFFER
from fmo.idempotency import combo_models_idempotency_key as _combo_models_idempotency_key
from fmo.idempotency import hash_parts, utcnow
from fmo.omniroute import OmniRouteRequestError
from fmo.pipeline import PipelineContext, StageResult
from fmo.quota_normalize import remaining_amount
from fmo.smart_review import ComboReviewResult, build_combo_review_context, run_combo_review

from ._base import StageDependencies
from ._helpers import _effect_result

APPLY_STAGE_EVIDENCE_MAX_AGE = timedelta(days=1)


def _diff_stage(dependencies: StageDependencies, context: PipelineContext) -> StageResult:
    current = _read_current_combos(dependencies.omniroute_client)
    with context.repository.database.transaction() as transaction:
        plans = transaction.execute(
            """
            SELECT DISTINCT ON (role_id) role_id, targets, constraint_report
            FROM allocation_plans
            ORDER BY role_id, created_at DESC
            """
        ).fetchall()
        written = 0
        for plan in plans:
            combo_id = _managed_combo_id(str(plan["role_id"]))
            desired = [_target_combo_step(target) for target in plan["targets"]]
            desired_endpoint_ids = [_target_endpoint_id(target) for target in plan["targets"]]
            before = current.get(combo_id, [])
            before_endpoint_ids = [member for member in before if isinstance(member, str)]
            before_keys = {_combo_member_key(member) for member in before}
            diff = {
                "combo_id": combo_id,
                "before": before,
                "after": desired,
                "before_endpoint_ids": before_endpoint_ids,
                "after_endpoint_ids": desired_endpoint_ids,
                "add": [
                    endpoint_id
                    for endpoint_id, step in zip(desired_endpoint_ids, desired, strict=True)
                    if _combo_member_key(step) not in before_keys
                ],
                "remove": [member for member in before_endpoint_ids if member not in desired_endpoint_ids],
            }
            review = _review_diff(dependencies, diff, plan=plan, transaction=transaction, run_id=context.run_id)
            context.repository.combo_snapshots.upsert(
                transaction,
                role_id=plan["role_id"],
                omniroute_combo_id=combo_id,
                state_hash=hash_parts(combo_id, str(diff)),
                state_json={**diff, "advisory_review": _review_payload(review)},
                phase="diff",
                run_id=context.run_id,
            )
            written += 1
    return _effect_result("diff", changed=written > 0)


def _review_diff(
    dependencies: StageDependencies,
    diff: dict[str, Any],
    *,
    plan: Any | None = None,
    transaction: Any = None,
    run_id: Any = None,
) -> ComboReviewResult:
    if dependencies.config is not None and dependencies.config.llm_smart_review_call_limit == 0:
        return run_combo_review(lambda _payload: {}, review_context={}, trigger=False)
    if dependencies.llm_runtime is None:
        return ComboReviewResult(status="failed", valid_diffs=[], rejected=[])
    targets = list(plan["targets"]) if plan is not None else []
    review_context = build_combo_review_context(
        role_id=str(plan["role_id"]) if plan is not None else str(diff["combo_id"]).removeprefix("fmo-"),
        current_combo=list(diff.get("before", [])),
        target_combo=list(diff.get("after", [])),
        deterministic_diff=diff,
        targets=targets,
        constraint_report=dict(plan["constraint_report"] or {}) if plan is not None else {},
        run_id=run_id,
        transaction=transaction,
    )
    return run_combo_review(dependencies.llm_runtime, review_context=review_context, trigger=True)


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
        diffs = _latest_diff_snapshots(transaction)
        minimum_safety_buffer = (
            dependencies.config.apply_min_safety_buffer
            if dependencies.config is not None
            else DEFAULT_APPLY_MIN_SAFETY_BUFFER
        )
        minimum_percent_remaining = (
            dependencies.config.apply_min_percent_remaining
            if dependencies.config is not None
            else DEFAULT_APPLY_MIN_PERCENT_REMAINING
        )
        safety = _derive_apply_stage_safety(
            transaction,
            diffs,
            minimum_safety_buffer=minimum_safety_buffer,
            minimum_percent_remaining=minimum_percent_remaining,
        )
    try:
        check_apply_preconditions(
            ApplyPreconditions(
                db_available=True,
                snapshot_saved=bool(diffs),
                desired_state_valid=all(isinstance(diff["state_json"].get("after"), list) for diff in diffs),
                quota_safe=safety["quota_safe"],
                probes_passed=safety["probes_passed"],
            )
        )
    except ValueError as exc:
        return StageResult(status="unsafe_to_apply", reason=str(exc))

    current_states = _read_current_combo_states(dependencies.omniroute_client)
    current = {combo_id: list(state["models"]) for combo_id, state in current_states.items()}
    applier = ComboApplier(current={combo_id: list(models) for combo_id, models in current.items()})
    combo_test_called = False
    applied = []
    unmanaged_combos = []
    dry_run = bool(context.config.get("dry_run", False))
    for diff in diffs:
        combo_id = diff["omniroute_combo_id"]
        diff_before = list(diff["state_json"].get("before", []))
        desired = list(diff["state_json"].get("after", []))
        if not combo_id.startswith("fmo-"):
            continue
        # AICODE-NOTE: Live OmniRoute combo set is source of truth for whether
        # apply may rebalance; absent desired combos are operator-managed setup.
        if combo_id not in current_states:
            unmanaged_combos.append(combo_id)
            continue
        live_state = current_states[combo_id]
        live_baseline = list(live_state["models"])
        write_id = str(live_state["write_id"])
        if live_baseline != diff_before:
            return StageResult(
                status="unsafe_to_apply",
                reason="combo_drift_detected",
                details={"combo_test_called": combo_test_called, "unmanaged_combos": unmanaged_combos},
            )
        if dry_run:
            continue
        expected_hash = applier.state_hash(combo_id)
        # AICODE-NOTE: desired is already structured OmniRoute model steps;
        # after_endpoint_ids carries the stable FMO audit/safety keys.
        dependencies.omniroute_client.put(
            f"/api/combos/{write_id}",
            {"models": desired},
            idempotency_key=expected_hash,
        )
        smoke_ok = _smoke_combo(dependencies.omniroute_client, combo_id)
        combo_test_called = True
        applier.apply(combo_id, desired, expected_hash=expected_hash, smoke_ok=smoke_ok)
        if not smoke_ok:
            if not _rollback_apply_mutations(
                dependencies.omniroute_client,
                applied,
                failed=(combo_id, write_id, live_baseline),
            ):
                return StageResult(
                    status="rollback_failed", reason="rollback_failed", details={"combo_test_called": True}
                )
            _delete_applied_snapshots_for_run(context, applied)
            return StageResult(
                status="apply_failed_rolled_back", reason="smoke_failed", details={"combo_test_called": True}
            )
        _persist_applied_snapshot(context, diff, live_baseline, desired)
        applied.append((diff, live_baseline, desired, write_id))
    if dry_run:
        return StageResult(
            status="success",
            changed=False,
            idempotency_key="apply:dry-run",
            details={
                "combo_test_called": False,
                "effect": "idempotent_no_change",
                "unmanaged_combos": unmanaged_combos,
            },
        )
    result = _effect_result("apply", changed=bool(applied))
    return StageResult(
        status=result.status,
        idempotency_key=result.idempotency_key,
        changed=result.changed,
        details={**result.details, "combo_test_called": combo_test_called, "unmanaged_combos": unmanaged_combos},
    )


def _latest_diff_snapshots(transaction: Any) -> list[Any]:
    return transaction.execute(
        """
        SELECT DISTINCT ON (role_id) id, role_id, omniroute_combo_id, state_json
        FROM combo_snapshots
        WHERE phase = 'diff'
          AND omniroute_combo_id LIKE 'fmo-%'
        ORDER BY role_id, created_at DESC
        """
    ).fetchall()


def _persist_applied_snapshot(context: PipelineContext, diff: Any, before: list[Any], desired: list[Any]) -> None:
    with context.repository.database.transaction() as transaction:
        context.repository.combo_snapshots.upsert(
            transaction,
            role_id=diff["role_id"],
            omniroute_combo_id=diff["omniroute_combo_id"],
            state_hash=hash_parts(diff["omniroute_combo_id"], str(desired), "applied", str(context.run_id)),
            state_json={"before": before, "after": desired},
            phase="applied",
            run_id=context.run_id,
        )


def _rollback_apply_mutations(
    client: Any,
    applied: Sequence[tuple[Any, list[Any], list[Any], str]],
    *,
    failed: tuple[str, str, list[Any]],
) -> bool:
    rollback_targets = [(failed[0], failed[1], failed[2])]
    rollback_targets.extend(
        (diff["omniroute_combo_id"], write_id, before) for diff, before, _desired, write_id in reversed(applied)
    )
    rollback_failed = False
    for combo_id, write_id, before in rollback_targets:
        try:
            client.put(
                f"/api/combos/{write_id}",
                {"models": before},
                idempotency_key=_combo_models_idempotency_key(combo_id, before),
            )
        except Exception:
            rollback_failed = True
    return not rollback_failed


def _delete_applied_snapshots_for_run(
    context: PipelineContext,
    applied: Sequence[tuple[Any, list[Any], list[Any], str]],
) -> None:
    if not applied:
        return
    with context.repository.database.transaction() as transaction:
        transaction.execute(
            """
            DELETE FROM combo_snapshots
            WHERE run_id = %(run_id)s
              AND phase = 'applied'
            """,
            {"run_id": context.run_id},
        )


def _derive_apply_stage_safety(
    transaction: Any,
    diffs: Sequence[Any],
    *,
    minimum_safety_buffer: float,
    minimum_percent_remaining: float,
) -> dict[str, bool]:
    endpoint_ids = _desired_apply_endpoint_ids(diffs)
    if not endpoint_ids:
        return {"quota_safe": True, "probes_passed": True}
    return {
        "quota_safe": _desired_endpoints_have_current_quota_safety(
            transaction,
            endpoint_ids,
            minimum_safety_buffer=minimum_safety_buffer,
            minimum_percent_remaining=minimum_percent_remaining,
        ),
        "probes_passed": _desired_endpoints_have_current_probe_success(transaction, endpoint_ids),
    }


def _desired_apply_endpoint_ids(diffs: Sequence[Any]) -> list[str]:
    endpoint_ids = set()
    for diff in diffs:
        desired = diff["state_json"].get("after_endpoint_ids")
        if not isinstance(desired, list):
            continue
        endpoint_ids.update(str(endpoint_id) for endpoint_id in desired)
    return sorted(endpoint_ids)


def _desired_endpoints_have_current_quota_safety(
    transaction: Any,
    endpoint_ids: Sequence[str],
    *,
    minimum_safety_buffer: float,
    minimum_percent_remaining: float,
) -> bool:
    rows = transaction.execute(
        """
        SELECT eas.endpoint_id, eas.effective_remaining, eas.hard_stop_capable, eas.evidence,
               eas.reset_at, eas.classified_at, eas.valid_until, eas.status,
               qr.limits AS quota_rule_limits
        FROM endpoint_access_states eas
        LEFT JOIN quota_rules qr ON qr.id = eas.quota_rule_id
        WHERE eas.endpoint_id::text = ANY(%(endpoint_ids)s)
        """,
        {"endpoint_ids": list(endpoint_ids)},
    ).fetchall()
    if len(rows) != len(endpoint_ids):
        return False
    now = utcnow()
    oldest_allowed = now - APPLY_STAGE_EVIDENCE_MAX_AGE
    return all(
        _endpoint_quota_row_is_safe(
            row,
            now=now,
            oldest_allowed=oldest_allowed,
            minimum_safety_buffer=minimum_safety_buffer,
            minimum_percent_remaining=minimum_percent_remaining,
        )
        for row in rows
    )


def _endpoint_quota_row_is_safe(
    row: Any,
    *,
    now: datetime,
    oldest_allowed: datetime,
    minimum_safety_buffer: float,
    minimum_percent_remaining: float,
) -> bool:
    evidence = row["evidence"] if isinstance(row["evidence"], dict) else {}
    safety_buffer = max(float(evidence.get("safety_buffer") or 0), minimum_safety_buffer)
    percent_remaining = evidence.get("percent_remaining")
    has_known_daily_budget = (
        evidence.get("remaining_source") == "live_observed"
        and evidence.get("daily_budget_source") in {"research", "calibration"}
        and isinstance(percent_remaining, int | float)
        and float(percent_remaining) > minimum_percent_remaining
    )
    has_request_window_budget = _request_window_rule_is_safe(row, evidence=evidence)
    return (
        row["status"] == "confirmed"
        and row["hard_stop_capable"] is True
        and (has_known_daily_budget or has_request_window_budget)
        and (has_request_window_budget or evidence.get("locked_out") is not True)
        and remaining_amount(row["effective_remaining"]) > safety_buffer
        and (has_request_window_budget or row["reset_at"] is None or row["reset_at"] <= now)
        and row["classified_at"] >= oldest_allowed
        and (row["valid_until"] is None or row["valid_until"] > now)
    )


def _request_window_rule_is_safe(row: Any, *, evidence: dict[str, Any]) -> bool:
    limits = row["quota_rule_limits"] if isinstance(row["quota_rule_limits"], dict) else {}
    return (
        evidence.get("remaining_source") in {"assumed", "live_observed"}
        and evidence.get("quota_rule") is True
        and evidence.get("daily_budget_source") == "research"
        and evidence.get("hard_stop") is True
        and limits.get("window") in {"minute", "hour"}
        and isinstance(limits.get("requests"), int | float)
    )


def _desired_endpoints_have_current_probe_success(transaction: Any, endpoint_ids: Sequence[str]) -> bool:
    rows = transaction.execute(
        """
        SELECT DISTINCT ON (endpoint_id) endpoint_id, passed, finished_at
        FROM endpoint_probes
        WHERE endpoint_id::text = ANY(%(endpoint_ids)s)
        ORDER BY endpoint_id, finished_at DESC
        """,
        {"endpoint_ids": list(endpoint_ids)},
    ).fetchall()
    if len(rows) != len(endpoint_ids):
        return False
    oldest_allowed = utcnow() - APPLY_STAGE_EVIDENCE_MAX_AGE
    return all(row["passed"] is True and row["finished_at"] >= oldest_allowed for row in rows)


def _smoke_combo(client: Any, combo_id: str) -> bool:
    try:
        response = client.post(
            "/v1/chat/completions",
            {"model": combo_id, "messages": [{"role": "user", "content": "Return ok"}]},
        )
    except OmniRouteRequestError:
        return False
    choices = response.get("choices", []) if isinstance(response, dict) else []
    if not choices or not isinstance(choices[0], dict):
        return False
    message = choices[0].get("message")
    if not isinstance(message, dict):
        return False
    return bool(str(message.get("content") or "").strip())


def _read_current_combos(client: Any | None) -> dict[str, list[Any]]:
    return {combo_id: list(state["models"]) for combo_id, state in _read_current_combo_states(client).items()}


def _read_current_combo_states(client: Any | None) -> dict[str, dict[str, Any]]:
    if client is None or not hasattr(client, "get"):
        return {}
    payload = client.get("/api/combos")
    combos = payload.get("combos", []) if isinstance(payload, dict) else []
    current: dict[str, dict[str, Any]] = {}
    for combo in combos:
        if not isinstance(combo, dict):
            continue
        combo_key = _live_combo_key(combo)
        if combo_key is None:
            continue
        current[combo_key] = {
            "write_id": _live_combo_write_id(combo, combo_key),
            "models": [_normalize_combo_member(model) for model in combo.get("models", [])],
        }
    return current


def _live_combo_key(combo: dict[str, Any]) -> str | None:
    # AICODE-NOTE: Live OmniRoute uses UUID `id` plus human `name`; the bridge
    # lists managed combos by name, while writes may require the UUID `id`.
    for field in ("name", "id"):
        value = str(combo.get(field) or "")
        if value.startswith("fmo-"):
            return value
    return None


def _live_combo_write_id(combo: dict[str, Any], combo_key: str) -> str:
    return str(combo.get("id") or combo_key)


def _managed_combo_id(role_id: str) -> str:
    return role_id if role_id.startswith("fmo-") else f"fmo-{role_id}"


def _target_combo_step(target: dict[str, Any]) -> dict[str, Any]:
    step = target["combo_step"]
    if not isinstance(step, dict):
        raise ValueError("allocation target missing structured combo_step")
    return {key: value for key, value in step.items() if value is not None}


def _target_endpoint_id(target: dict[str, Any]) -> str:
    endpoint_id = target["endpoint_id"]
    if not endpoint_id:
        raise ValueError("allocation target missing endpoint_id")
    return str(endpoint_id)


def _normalize_combo_member(member: Any) -> Any:
    if not isinstance(member, dict):
        return str(member)
    normalized = {str(key): value for key, value in member.items() if value is not None}
    if normalized.get("kind") == "model" and "weight" not in normalized:
        normalized["weight"] = 0
    return normalized


def _combo_member_key(member: Any) -> str:
    if not isinstance(member, dict):
        return str(member)
    provider = member.get("providerId", "")
    connection = member.get("connectionId", "")
    model = member.get("model", "")
    return f"{provider}:{connection}:{model}"
