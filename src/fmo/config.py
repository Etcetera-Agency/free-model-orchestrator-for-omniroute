from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class StartupConfig:
    omniroute_url: str
    database_url: str | None
    hermes_inventory_mode: str
    hermes_home: str | None = None
    hermes_agents_path: str | None = None
    hermes_routines_path: str | None = None
    hermes_inventory_command: str | None = None
    hermes_inventory_url: str | None = None
    hermes_inventory_cron: str = "0 4 * * *"


def validate_startup(config: StartupConfig, *, health_check, model_endpoint_check=None) -> dict:
    validate_static_config(config)
    health = health_check()
    if not isinstance(health, dict):
        raise ValueError("OmniRoute health check returned non-object payload")
    return health


def validate_static_config(config: StartupConfig) -> None:
    if urlparse(config.omniroute_url).scheme not in {"http", "https"}:
        raise ValueError("OMNIROUTE_URL must be http or https")
    if not config.database_url:
        raise ValueError("DATABASE_URL is required")
    if config.hermes_inventory_mode not in {"filesystem", "command", "http"}:
        raise ValueError("HERMES_INVENTORY_MODE is invalid")
    if not _valid_cron(config.hermes_inventory_cron):
        raise ValueError("HERMES_INVENTORY_CRON is invalid")
    if config.hermes_inventory_mode == "filesystem":
        missing = [
            name
            for name, value in (
                ("HERMES_HOME", config.hermes_home),
                ("HERMES_AGENTS_PATH", config.hermes_agents_path),
                ("HERMES_ROUTINES_PATH", config.hermes_routines_path),
            )
            if not value
        ]
        if missing:
            raise ValueError(f"missing filesystem inventory config: {', '.join(missing)}")
    if config.hermes_inventory_mode == "command" and not config.hermes_inventory_command:
        raise ValueError("HERMES_INVENTORY_COMMAND is required")
    if config.hermes_inventory_mode == "http":
        parsed = urlparse(config.hermes_inventory_url or "")
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("HERMES_INVENTORY_URL must be http or https")


def _valid_cron(value: str) -> bool:
    parts = value.split()
    if len(parts) != 5:
        return False
    return all(part for part in parts)
