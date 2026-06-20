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


def _requires_apply_preconditions(argv: Sequence[str]) -> bool:
    return any(arg == "apply" for arg in argv)


def _apply_preconditions_ok(config: StartupConfig) -> bool:
    if config.database_url is None:
        return False
    try:
        repository = Repository(Database(config.database_url))
        with repository.database.transaction() as transaction:
            preconditions = ApplyPreconditions(
                db_available=_database_available(transaction),
                snapshot_saved=_snapshot_saved(transaction),
                desired_state_valid=_desired_state_valid(transaction),
                quota_safe=_quota_safe(transaction),
                probes_passed=_probes_passed(transaction),
            )
        check_apply_preconditions(preconditions)
    except Exception:
        return False
    return True


def _database_available(transaction: Any) -> bool:
    transaction.execute("SELECT 1")
    return True


def _snapshot_saved(transaction: Any) -> bool:
    row = transaction.execute(
        """
        SELECT 1
        FROM combo_snapshots
        WHERE phase IN ('current', 'planned')
        LIMIT 1
        """
    ).fetchone()
    return row is not None


def _desired_state_valid(transaction: Any) -> bool:
    row = transaction.execute(
        """
        SELECT 1
        FROM allocation_plans
        WHERE status IN ('planned', 'validated')
          AND jsonb_array_length(targets) > 0
        LIMIT 1
        """
    ).fetchone()
    return row is not None


def _quota_safe(transaction: Any) -> bool:
    row = transaction.execute(
        """
        SELECT constraint_report
        FROM allocation_plans
        WHERE status IN ('planned', 'validated')
        ORDER BY created_at DESC
        LIMIT 1
        """
    ).fetchone()
    if row is None:
        return False
    report = row["constraint_report"]
    return isinstance(report, dict) and report.get("ok") is True and report.get("quota_safe") is not False


def _probes_passed(transaction: Any) -> bool:
    row = transaction.execute(
        """
        SELECT bool_and(passed) AS passed, count(*) AS total
        FROM endpoint_probes
        """
    ).fetchone()
    return row is not None and row["total"] > 0 and row["passed"] is True
