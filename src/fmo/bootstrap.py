from __future__ import annotations

import os
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from fmo.apply_guard import ApplyPreconditions, check_apply_preconditions
from fmo.config import StartupConfig, validate_startup
from fmo.omniroute import OmniRouteClient
from fmo.persistence import Database, Repository

Dispatcher = Callable[[list[str], bool, StartupConfig], int]


def build_startup_config(env: Mapping[str, str] | None = None) -> StartupConfig:
    values = env or os.environ
    return StartupConfig(
        omniroute_url=values.get("OMNIROUTE_URL", ""),
        database_url=_empty_to_none(values.get("DATABASE_URL")),
        omniroute_api_key=_empty_to_none(values.get("OMNIROUTE_API_KEY")),
        llm_bootstrap_model_id=_empty_to_none(values.get("LLM_BOOTSTRAP_MODEL_ID")),
        llm_bootstrap_confirmed_free=_truthy(values.get("LLM_BOOTSTRAP_MODEL_CONFIRMED_FREE")),
        llm_quota_research_call_limit=_non_negative_int(values.get("LLM_QUOTA_RESEARCH_CALL_LIMIT"), 1),
        llm_smart_review_call_limit=_non_negative_int(values.get("LLM_SMART_REVIEW_CALL_LIMIT"), 1),
        apply_min_safety_buffer=_positive_float(values.get("APPLY_MIN_SAFETY_BUFFER"), 1.0),
        apply_min_percent_remaining=_positive_float(values.get("APPLY_MIN_PERCENT_REMAINING"), 1.0),
        hermes_inventory_mode=values.get("HERMES_INVENTORY_MODE", "filesystem"),
        hermes_home=_empty_to_none(values.get("HERMES_HOME")),
        hermes_agents_path=_empty_to_none(values.get("HERMES_AGENTS_PATH")),
        hermes_routines_path=_empty_to_none(values.get("HERMES_ROUTINES_PATH")),
        hermes_inventory_command=_empty_to_none(values.get("HERMES_INVENTORY_COMMAND")),
        hermes_inventory_url=_empty_to_none(values.get("HERMES_INVENTORY_URL")),
        hermes_inventory_cron=values.get("HERMES_INVENTORY_CRON", "0 4 * * *"),
    )


def bootstrap_and_dispatch(
    argv: Sequence[str],
    *,
    env: Mapping[str, str] | None = None,
    health_check: Callable[[], dict] | None = None,
    dispatcher: Dispatcher,
) -> int:
    try:
        config = build_startup_config(env)
        validate_startup(config, health_check=health_check or _health_check(config))
    except ValueError:
        return 3
    preconditions_ok = _apply_preconditions_ok(config) if _requires_apply_preconditions(argv) else True
    return dispatcher(list(argv), preconditions_ok, config)


def _health_check(config: StartupConfig) -> Callable[[], dict]:
    def check() -> dict:
        client = OmniRouteClient(base_url=config.omniroute_url, api_key=config.omniroute_api_key)
        return client.get("/api/monitoring/health")

    return check


def _empty_to_none(value: str | None) -> str | None:
    return value or None


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _non_negative_int(value: str | None, default: int) -> int:
    if value is None or value == "":
        return default
    return int(value)


def _positive_float(value: str | None, default: float) -> float:
    if value is None or value == "":
        return default
    return float(value)


def _requires_apply_preconditions(argv: Sequence[str]) -> bool:
    return any(arg == "apply" for arg in argv)


def _apply_preconditions_ok(config: StartupConfig) -> bool:
    if config.database_url is None:
        return False
    from fmo.composition_stages.apply import _derive_apply_stage_safety

    try:
        repository = Repository(Database(config.database_url))
        with repository.database.transaction() as transaction:
            diffs = _latest_apply_diffs(transaction)
            safety = _derive_apply_stage_safety(
                transaction,
                diffs,
                minimum_safety_buffer=config.apply_min_safety_buffer,
                minimum_percent_remaining=config.apply_min_percent_remaining,
            )
            preconditions = ApplyPreconditions(
                db_available=_database_available(transaction),
                snapshot_saved=bool(diffs),
                desired_state_valid=all(isinstance(diff["state_json"].get("after"), list) for diff in diffs),
                quota_safe=safety["quota_safe"],
                probes_passed=safety["probes_passed"],
            )
        check_apply_preconditions(preconditions)
    except Exception:
        return False
    return True


def _database_available(transaction: Any) -> bool:
    transaction.execute("SELECT 1")
    return True


def _latest_apply_diffs(transaction: Any) -> list[Any]:
    return transaction.execute(
        """
        SELECT DISTINCT ON (omniroute_combo_id) id, role_id, omniroute_combo_id, state_json
        FROM combo_snapshots
        WHERE phase = 'diff'
          AND omniroute_combo_id LIKE 'fmo-%'
        ORDER BY omniroute_combo_id, created_at DESC
        """
    ).fetchall()
