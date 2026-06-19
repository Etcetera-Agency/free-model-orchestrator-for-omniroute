from __future__ import annotations

import os
from collections.abc import Callable, Mapping, Sequence

from fmo.config import StartupConfig, validate_startup
from fmo.omniroute import OmniRouteClient


Dispatcher = Callable[[list[str], bool, StartupConfig], int]


def build_startup_config(env: Mapping[str, str] | None = None) -> StartupConfig:
    values = env or os.environ
    return StartupConfig(
        omniroute_url=values.get("OMNIROUTE_URL", ""),
        database_url=_empty_to_none(values.get("DATABASE_URL")),
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
    return dispatcher(list(argv), True, config)


def _health_check(config: StartupConfig) -> Callable[[], dict]:
    def check() -> dict:
        client = OmniRouteClient(base_url=config.omniroute_url, api_key=os.environ.get("OMNIROUTE_API_KEY"))
        return client.get("/api/monitoring/health")

    return check


def _empty_to_none(value: str | None) -> str | None:
    return value or None
