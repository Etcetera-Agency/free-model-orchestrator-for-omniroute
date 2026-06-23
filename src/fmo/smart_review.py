import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from fmo.llm_runtime import LlmSiteConfig, complete_with_adapter

ALLOWED_OPS = {"add", "remove", "move"}
PROMPTS_DIR = Path(__file__).resolve().parents[2] / "reference" / "prompts"
SMART_COMBO_REVIEWER_PROMPT = PROMPTS_DIR / "smart-combo-reviewer.md"
REQUIRED_CONTEXT_SECTIONS = (
    "role_id",
    "current_combo",
    "target_combo",
    "deterministic_diff",
    "role_requirements",
    "demand_forecast",
    "allocation_constraint_report",
    "candidate_registry",
    "quota_summary",
    "diversity_summary",
    "validation_report",
    "apply_precondition_summary",
)


@dataclass(frozen=True)
class ComboReviewResult:
    status: str
    valid_diffs: list[dict]
    rejected: list[dict]
    combo_test_called: bool = False


class ComboReviewResponse(BaseModel):
    diffs: list[dict] = Field(default_factory=list)


def build_combo_review_context(
    *,
    role_id: str,
    current_combo: list[Any],
    target_combo: list[Any],
    deterministic_diff: dict[str, Any],
    targets: list[dict[str, Any]],
    constraint_report: dict[str, Any],
    run_id: Any = None,
    transaction: Any = None,
    max_candidates: int = 24,
) -> dict[str, Any]:
    # AICODE-NOTE: Reviewer context is deterministic input only; LLM advice
    # never mutates the diff unless later deterministic validation accepts it.
    role_requirements, demand_forecast = _role_facts(transaction, role_id)
    candidate_registry = _candidate_registry(targets, max_candidates=max_candidates)
    context = {
        "role_id": role_id,
        "run": {"run_id": str(run_id) if run_id is not None else None, "schema_version": 1},
        "current_combo": current_combo,
        "target_combo": target_combo,
        "deterministic_diff": deterministic_diff,
        "role_requirements": role_requirements,
        "demand_forecast": demand_forecast,
        "allocation_constraint_report": constraint_report,
        "candidate_registry": candidate_registry,
        "quota_summary": _quota_summary(transaction, [target["endpoint_id"] for target in targets]),
        "diversity_summary": constraint_report.get("diversity", {}),
        "validation_report": _validation_report(deterministic_diff, constraint_report),
        "apply_precondition_summary": _apply_precondition_summary(targets),
    }
    return _redact_context(context)


def run_combo_review(instructor_call, *, review_context: dict[str, Any], trigger: bool) -> ComboReviewResult:
    if not trigger:
        return ComboReviewResult(status="skipped_trigger", valid_diffs=[], rejected=[])
    try:
        site = LlmSiteConfig(
            name="smart-combo-reviewer",
            model="omniroute/free-reviewer",
            prompt_path=SMART_COMBO_REVIEWER_PROMPT,
            max_prompt_chars=5000,
            advisory=True,
        )
        context = {"review_brief": json.dumps(_redact_context(review_context), sort_keys=True)}
        if hasattr(instructor_call, "complete"):
            response = instructor_call.complete(site=site, context=context, response_model=ComboReviewResponse)
        else:
            response = complete_with_adapter(
                instructor_call,
                site=site,
                context=context,
                response_model=ComboReviewResponse,
            )
    except Exception:
        return ComboReviewResult(status="failed", valid_diffs=[], rejected=[])
    valid = []
    rejected = []
    for diff in response.diffs:
        if diff.get("op") not in ALLOWED_OPS:
            rejected.append({"diff": diff, "reason": "forbidden_op"})
        else:
            valid.append(diff)
    status = "ok" if valid else "no_valid_diffs"
    return ComboReviewResult(status=status, valid_diffs=valid, rejected=rejected)


def _role_facts(transaction: Any, role_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    if transaction is None:
        return {}, {}
    role = transaction.execute(
        "SELECT requirements, expected_load, criticality FROM roles WHERE id = %(role_id)s",
        {"role_id": role_id},
    ).fetchone()
    forecast = transaction.execute(
        """
        SELECT protected_requests, expected_requests, confidence, demand_source
        FROM role_demand_forecasts
        WHERE role_id = %(role_id)s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        {"role_id": role_id},
    ).fetchone()
    requirements = dict(role["requirements"] or {}) if role else {}
    if role:
        requirements["criticality"] = int(role["criticality"])
        requirements["expected_load"] = dict(role["expected_load"] or {})
    demand = (
        {
            "protected_requests": float(forecast["protected_requests"]),
            "expected_requests": float(forecast["expected_requests"]),
            "confidence": float(forecast["confidence"]),
            "demand_source": forecast["demand_source"],
        }
        if forecast
        else {}
    )
    return requirements, demand


def _candidate_registry(targets: list[dict[str, Any]], *, max_candidates: int) -> dict[str, Any]:
    ranked = sorted(targets, key=lambda target: (-float(target.get("score") or 0), str(target.get("endpoint_id"))))
    candidates = [
        {
            "endpoint_id": target.get("endpoint_id"),
            "combo_step": target.get("combo_step"),
            "groups": target.get("groups", {}),
            "score": target.get("score"),
        }
        for target in ranked[:max_candidates]
    ]
    return {
        "candidates": candidates,
        "total_candidates": len(targets),
        "omitted_candidates": max(len(targets) - len(candidates), 0),
        "summary": "bounded_by_score_then_endpoint",
    }


def _quota_summary(transaction: Any, endpoint_ids: list[Any]) -> dict[str, Any]:
    if transaction is None or not endpoint_ids:
        return {"endpoints": []}
    rows = transaction.execute(
        """
        SELECT endpoint_id, status, effective_remaining, hard_stop_capable, evidence
        FROM endpoint_access_states
        WHERE endpoint_id::text = ANY(%(endpoint_ids)s)
        """,
        {"endpoint_ids": [str(endpoint_id) for endpoint_id in endpoint_ids]},
    ).fetchall()
    return {
        "endpoints": [
            {
                "endpoint_id": str(row["endpoint_id"]),
                "status": row["status"],
                "effective_remaining": row["effective_remaining"],
                "hard_stop_capable": row["hard_stop_capable"],
                "remaining_source": (row["evidence"] or {}).get("remaining_source")
                if isinstance(row["evidence"], dict)
                else None,
            }
            for row in rows
        ]
    }


def _validation_report(deterministic_diff: dict[str, Any], constraint_report: dict[str, Any]) -> dict[str, Any]:
    return {
        "diff_has_target": bool(deterministic_diff.get("after")),
        "allocation_apply": bool(constraint_report.get("apply")),
        "reason": constraint_report.get("reason"),
        "role_status": constraint_report.get("role_status"),
    }


def _apply_precondition_summary(targets: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "target_count": len(targets),
        "has_structured_steps": all(isinstance(target.get("combo_step"), dict) for target in targets),
        "has_endpoint_ids": all(bool(target.get("endpoint_id")) for target in targets),
    }


def _redact_context(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _redact_context(item) for key, item in value.items() if not _secret_like(str(key))}
    if isinstance(value, list):
        return [_redact_context(item) for item in value]
    if isinstance(value, str) and _secret_like(value):
        return "[REDACTED]"
    return value


def _secret_like(value: str) -> bool:
    upper = value.upper()
    return any(marker in upper for marker in ("API_KEY", "TOKEN", "SECRET", "COOKIE", "DATABASE_URL", "BEARER "))


def apply_review_diffs(
    combo: dict[str, list[str]],
    diffs: list[dict],
    *,
    candidate_registry: set[str],
    minimum_combo_size: int,
) -> tuple[dict[str, list[str]], dict[str, list[dict]]]:
    working = {role: list(endpoints) for role, endpoints in combo.items()}
    rejected = []
    for diff in diffs:
        try:
            _apply_one(working, diff, candidate_registry=candidate_registry, minimum_combo_size=minimum_combo_size)
        except ValueError as exc:
            rejected.append({"diff": diff, "reason": str(exc)})
    return working, {"rejected": rejected}


def _apply_one(
    combo: dict[str, list[str]], diff: dict, *, candidate_registry: set[str], minimum_combo_size: int
) -> None:
    role = diff["role"]
    endpoints = combo.setdefault(role, [])
    endpoint_id = diff["endpoint_id"]
    if diff["op"] == "add":
        if endpoint_id not in candidate_registry:
            raise ValueError("unknown_endpoint")
        position = min(diff.get("position", len(endpoints)), len(endpoints))
        if endpoint_id not in endpoints:
            endpoints.insert(position, endpoint_id)
    elif diff["op"] == "remove":
        if endpoint_id not in endpoints:
            raise ValueError("endpoint_missing")
        if len(endpoints) - 1 < minimum_combo_size:
            raise ValueError("minimum_combo_size")
        endpoints.remove(endpoint_id)
    elif diff["op"] == "move":
        if endpoint_id not in endpoints:
            raise ValueError("endpoint_missing")
        endpoints.remove(endpoint_id)
        endpoints.insert(min(diff.get("position", len(endpoints)), len(endpoints)), endpoint_id)
    else:
        raise ValueError("forbidden_op")
