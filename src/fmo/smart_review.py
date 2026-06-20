import json
from dataclasses import dataclass

from pydantic import BaseModel, Field

from fmo.llm_runtime import LlmSiteConfig, complete_with_adapter


ALLOWED_OPS = {"add", "remove", "move"}


@dataclass(frozen=True)
class ComboReviewResult:
    status: str
    valid_diffs: list[dict]
    rejected: list[dict]
    combo_test_called: bool = False


class ComboReviewResponse(BaseModel):
    diffs: list[dict] = Field(default_factory=list)


def run_combo_review(instructor_call, *, deterministic_combo: dict[str, list[str]], trigger: bool) -> ComboReviewResult:
    if not trigger:
        return ComboReviewResult(status="skipped_trigger", valid_diffs=[], rejected=[])
    try:
        response = complete_with_adapter(
            instructor_call,
            site=LlmSiteConfig(
                name="smart-combo-reviewer",
                model="omniroute/free-reviewer",
                max_prompt_chars=5000,
                advisory=True,
            ),
            context={"prompt": json.dumps({"combo": deterministic_combo}, sort_keys=True)},
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


def _apply_one(combo: dict[str, list[str]], diff: dict, *, candidate_registry: set[str], minimum_combo_size: int) -> None:
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
