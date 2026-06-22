from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class StartupConfig:
    omniroute_url: str
    database_url: str | None
    hermes_inventory_mode: str
    omniroute_api_key: str | None = None
    llm_bootstrap_model_id: str | None = None
    llm_bootstrap_confirmed_free: bool = False
    llm_quota_research_call_limit: int = 1
    llm_smart_review_call_limit: int = 1
    tokens_per_request: int = 2000
    tokens_per_request_recalibration_cron: str = "0 5 * * 0"
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
    parsed_omniroute = urlparse(config.omniroute_url)
    if parsed_omniroute.scheme not in {"http", "https"}:
        raise ValueError("OMNIROUTE_URL must be http or https")
    if not config.omniroute_api_key:
        raise ValueError("OMNIROUTE_API_KEY is required")
    if config.llm_bootstrap_model_id and not config.llm_bootstrap_confirmed_free:
        raise ValueError("LLM_BOOTSTRAP_MODEL_CONFIRMED_FREE must be true when LLM_BOOTSTRAP_MODEL_ID is set")
    if config.llm_quota_research_call_limit < 0:
        raise ValueError("LLM_QUOTA_RESEARCH_CALL_LIMIT must be non-negative")
    if config.llm_smart_review_call_limit < 0:
        raise ValueError("LLM_SMART_REVIEW_CALL_LIMIT must be non-negative")
    if config.tokens_per_request <= 0:
        raise ValueError("TOKENS_PER_REQUEST must be positive")
    if not _valid_cron(config.tokens_per_request_recalibration_cron):
        raise ValueError("TOKENS_PER_REQUEST_RECALIBRATION_CRON is invalid")
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
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("HERMES_INVENTORY_URL must be http or https")


def _valid_cron(value: str) -> bool:
    parts = value.split(" ")
    if len(parts) != 5:
        return False
    return all(part for part in parts)
