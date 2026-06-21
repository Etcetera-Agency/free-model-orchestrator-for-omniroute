import json
import sqlite3
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import yaml
from pydantic import BaseModel

from fmo.llm_runtime import LlmSiteConfig, complete_with_adapter


@dataclass(frozen=True)
class Consumer:
    role_id: str
    consumer_type: str
    consumer: str
    cadence: str
    calls_per_run: float


@dataclass(frozen=True)
class Inventory:
    consumers: list[Consumer]


@dataclass(frozen=True)
class ProfileSlots:
    name: str
    path: str
    gateway_running: bool
    main_combo: str | None
    auxiliary: dict[str, Any]


@dataclass(frozen=True)
class HermesInventoryError(Exception):
    source: str
    reason: str
    detail: str | None = None


@dataclass(frozen=True)
class InventoryDiff:
    forecast_stale: bool
    run_inspector: bool

    def rebuild_combo(self, *, material_allocation_changed: bool) -> bool:
        return material_allocation_changed


@dataclass(frozen=True)
class InspectorForecast:
    role: str
    expected_calls: float
    average_input_tokens: float
    average_output_tokens: float
    confidence: str
    model_choice: None = None
    quota_change: None = None


class InspectorForecastResponse(BaseModel):
    role: str
    expected_calls: float
    average_input_tokens: float
    average_output_tokens: float
    confidence: str


def normalize_filesystem_inventory(payload: dict, *, env: dict[str, str]) -> Inventory:
    if not env.get("HERMES_HOME"):
        raise ValueError("HERMES_HOME is required")
    return _normalize(payload)


def normalize_command_inventory(payload: dict, *, env: dict[str, str]) -> Inventory:
    if not env.get("HERMES_INVENTORY_COMMAND"):
        raise ValueError("HERMES_INVENTORY_COMMAND is required")
    return _normalize(payload)


def normalize_http_inventory(payload: dict, *, env: dict[str, str]) -> Inventory:
    if not env.get("HERMES_INVENTORY_URL"):
        raise ValueError("HERMES_INVENTORY_URL is required")
    return _normalize(payload)


def should_run_full_inventory(*, observed_role: str, known_roles: set[str]) -> str | None:
    return "full" if observed_role not in known_roles else None


def inventory_diff(old: Inventory, new: Inventory) -> InventoryDiff:
    old_set = {(consumer.role_id, consumer.consumer_type, consumer.consumer, consumer.cadence, consumer.calls_per_run) for consumer in old.consumers}
    new_set = {(consumer.role_id, consumer.consumer_type, consumer.consumer, consumer.cadence, consumer.calls_per_run) for consumer in new.consumers}
    changed = old_set != new_set
    return InventoryDiff(forecast_stale=changed, run_inspector=changed)


def assemble_inspector_prompt(inventory: Inventory, *, changes: list[str], secrets: dict[str, str]) -> str:
    lines = ["Hermes inventory forecast request", "Changes:", *changes, "Consumers:"]
    for consumer in inventory.consumers:
        lines.append(f"{consumer.role_id} {consumer.consumer_type} {consumer.consumer} {consumer.cadence} {consumer.calls_per_run}")
    prompt = "\n".join(lines)
    for secret in secrets.values():
        prompt = prompt.replace(secret, "[REDACTED]")
    return prompt


def run_inspector(call_instructor, prompt: str) -> InspectorForecast:
    site = LlmSiteConfig(
        name="hermes-inspector",
        model="omniroute/free-inspector",
        max_prompt_chars=6000,
    )
    if hasattr(call_instructor, "complete"):
        payload = call_instructor.complete(site=site, context={"prompt": prompt}, response_model=InspectorForecastResponse)
    else:
        payload = complete_with_adapter(
            call_instructor,
            site=site,
            context={"prompt": prompt},
            response_model=InspectorForecastResponse,
        )
    return InspectorForecast(
        role=payload.role,
        expected_calls=payload.expected_calls,
        average_input_tokens=payload.average_input_tokens,
        average_output_tokens=payload.average_output_tokens,
        confidence=payload.confidence,
    )


def _normalize(payload: dict) -> Inventory:
    consumers = [
        Consumer(
            role_id=item["role"],
            consumer_type=item["consumer_type"],
            consumer=item["consumer"],
            cadence=item["cadence"],
            calls_per_run=item["calls_per_run"],
        )
        for item in payload.get("roles", [])
    ]
    return Inventory(consumers=consumers)


# ---------------------------------------------------------------------------
# Real Hermes source surfaces
#
# Shapes below mirror NousResearch/hermes-agent @ tag v2026.6.19 exactly:
#   - cron jobs:    ~/.hermes/cron/jobs.json -> {"jobs": [<job>], "updated_at"}
#                   each job: cron/jobs.py:create_job (schedule = parse_schedule)
#   - webhooks:     ~/.hermes/webhook_subscriptions.json -> {"<route>": <route>}
#                   route: hermes_cli/webhook.py:_cmd_subscribe
#   - profiles:     hermes profile list -> ProfileInfo (hermes_cli/profiles.py)
#                   gateway_running True => long-running service, else profile
#   - runtime:      ~/.hermes/state.db sessions table (hermes_state.py)
# No field is invented; absent values fall back to the documented defaults.
#
# The Hermes `model` field (cron job / profile config, and sessions.model in
# state.db) is NOT a raw model id — it is the OmniRoute *combo* the routine
# routes to. OmniRoute keeps exactly one combo per role (1:1), so the combo id
# is the role key for demand attribution.
# ---------------------------------------------------------------------------

# Role a consumer routes to when no combo override is set (gateway default combo).
DEFAULT_ROLE = "default"
# Event-driven and history-less consumers get a conservative bootstrap until the
# Inspector forecast or observed runtime demand refines them (see spec).
BOOTSTRAP_CALLS_PER_RUN = 1.0


def _combo_role(combo: Any) -> str:
    """Role key for an OmniRoute combo id (1:1), or the default combo's role."""
    return combo or DEFAULT_ROLE


def observe_session_demand(connection: sqlite3.Connection) -> dict[str, float]:
    """Average real `api_call_count` per role from state.db.

    `sessions.model` stores the OmniRoute combo the session ran against, which is
    the role key (one combo per role). Reads the runtime-observation source named
    by the hermes-inventory spec; roles with no observed sessions are absent.
    """
    cursor = connection.execute(
        "SELECT model, AVG(api_call_count) FROM sessions "
        "WHERE model IS NOT NULL AND api_call_count > 0 GROUP BY model"
    )
    return {row[0]: float(row[1]) for row in cursor.fetchall() if row[0]}


def parse_cron_jobs(payload: Any, *, demand_by_role: dict[str, float] | None = None) -> list[Consumer]:
    """Map `~/.hermes/cron/jobs.json` jobs to cron_job consumers."""
    demand_by_role = demand_by_role or {}
    jobs = payload.get("jobs", []) if isinstance(payload, dict) else (payload or [])
    consumers = []
    for job in jobs:
        if not job.get("enabled", True):
            continue  # paused/disabled jobs are not active demand
        role = _combo_role(job.get("model"))  # job["model"] is the OmniRoute combo
        consumers.append(
            Consumer(
                role_id=role,
                consumer_type="cron_job",
                consumer=job["id"],
                cadence=_cron_cadence(job.get("schedule") or {}),
                calls_per_run=demand_by_role.get(role, BOOTSTRAP_CALLS_PER_RUN),
            )
        )
    return consumers


def _cron_cadence(schedule: dict[str, Any]) -> str:
    kind = schedule.get("kind")
    if kind == "interval":
        return schedule.get("display") or f"every {schedule.get('minutes')}m"
    if kind == "cron":
        return schedule.get("expr") or schedule.get("display") or "cron"
    if kind == "once":
        return "once"
    return "unknown"


def parse_webhook_subscriptions(payload: Any, *, demand_by_role: dict[str, float] | None = None) -> list[Consumer]:
    """Map `~/.hermes/webhook_subscriptions.json` routes to webhook consumers."""
    demand_by_role = demand_by_role or {}
    consumers = []
    for name, route in (payload or {}).items():
        if route.get("enabled") is False:
            continue
        # Subscriptions carry no combo override; they route to the gateway
        # default combo's role. Cadence is event-driven (no fixed schedule).
        role = DEFAULT_ROLE
        events = route.get("events") or []
        cadence = f"event:{','.join(events)}" if events else "event-driven"
        consumers.append(
            Consumer(
                role_id=role,
                consumer_type="webhook",
                consumer=name,
                cadence=cadence,
                calls_per_run=demand_by_role.get(role, BOOTSTRAP_CALLS_PER_RUN),
            )
        )
    return consumers


def parse_profiles(payload: Any, *, demand_by_role: dict[str, float] | None = None) -> list[Consumer]:
    """Map `hermes profile list` ProfileInfo records to consumers.

    A profile whose gateway is running is a long-running `service`; otherwise it
    is an interactive `agent_profile`.
    """
    demand_by_role = demand_by_role or {}
    profiles = payload.get("profiles", []) if isinstance(payload, dict) else (payload or [])
    consumers = []
    for profile in profiles:
        slots = _profile_slots_from_record(profile)
        role = _combo_role(slots.main_combo)
        is_service = bool(profile.get("gateway_running"))
        consumers.append(
            Consumer(
                role_id=role,
                consumer_type="service" if is_service else "agent_profile",
                consumer=profile["name"],
                cadence="continuous" if is_service else "manual",
                calls_per_run=demand_by_role.get(role, BOOTSTRAP_CALLS_PER_RUN),
            )
        )
    return consumers


# AICODE-NOTE: ProfileInfo only enumerates name/path/gateway state; model slots
# come from each profile's config.yaml so auxiliary slots do not disappear.
def read_profile_slots(profile_info: dict[str, Any]) -> ProfileSlots:
    config_path = Path(profile_info["path"]) / "config.yaml"
    config = _read_yaml_file(config_path) or {}
    return _profile_slots_from_config(profile_info, config)


def parse_gateway_services(payload: Any, *, demand_by_role: dict[str, float] | None = None) -> list[Consumer]:
    demand_by_role = demand_by_role or {}
    config = payload or {}
    default_model = _combo_role(config.get("model"))
    platforms = (config.get("gateway") or {}).get("platforms") or {}
    consumers = []
    for name, platform in sorted(platforms.items()):
        if not platform.get("enabled"):
            continue
        role = _combo_role(platform.get("model") or default_model)
        consumers.append(
            Consumer(
                role_id=role,
                consumer_type="service",
                consumer=f"gateway:{name}",
                cadence="continuous",
                calls_per_run=demand_by_role.get(role, BOOTSTRAP_CALLS_PER_RUN),
            )
        )
    return consumers


def build_hermes_inventory(
    *,
    cron_jobs: Any = None,
    webhook_subscriptions: Any = None,
    profiles: Any = None,
    gateway_config: Any = None,
    session_connection: sqlite3.Connection | None = None,
) -> Inventory:
    """Combine real Hermes surfaces into one normalized Inventory."""
    demand_by_role = observe_session_demand(session_connection) if session_connection is not None else {}
    consumers: list[Consumer] = []
    if cron_jobs is not None:
        consumers += parse_cron_jobs(cron_jobs, demand_by_role=demand_by_role)
    if webhook_subscriptions is not None:
        consumers += parse_webhook_subscriptions(webhook_subscriptions, demand_by_role=demand_by_role)
    if profiles is not None:
        consumers += parse_profiles(profiles, demand_by_role=demand_by_role)
    if gateway_config is not None:
        consumers += parse_gateway_services(gateway_config, demand_by_role=demand_by_role)
    return Inventory(consumers=consumers)


def read_hermes_home(home: str | Path) -> Inventory:
    """Read a real `HERMES_HOME` directory layout into an Inventory.

    Reads `cron/jobs.json` and `webhook_subscriptions.json`, and opens
    `state.db` read-only for observed demand. Profiles are enumerated from the
    live profile directories and their `config.yaml` model values.
    """
    home = Path(home)
    jobs_file = home / "cron" / "jobs.json"
    subs_file = home / "webhook_subscriptions.json"
    state_db = home / "state.db"
    gateway_config = read_gateway_config(home)

    cron_jobs = json.loads(jobs_file.read_text()) if jobs_file.is_file() else None
    webhook_subscriptions = json.loads(subs_file.read_text()) if subs_file.is_file() else None
    profiles = enumerate_live_profiles(home)

    connection = None
    if state_db.is_file():
        connection = sqlite3.connect(f"file:{state_db}?mode=ro", uri=True)
    try:
        return build_hermes_inventory(
            cron_jobs=cron_jobs,
            webhook_subscriptions=webhook_subscriptions,
            profiles=profiles,
            gateway_config=gateway_config,
            session_connection=connection,
        )
    finally:
        if connection is not None:
            connection.close()


def read_hermes_command_sources(command: list[str], *, timeout: float = 10) -> dict:
    try:
        completed = subprocess.run(command, check=False, capture_output=True, text=True, timeout=timeout)
    except OSError as exc:
        raise HermesInventoryError("command", "execution_failed", str(exc)) from exc
    except subprocess.TimeoutExpired as exc:
        raise HermesInventoryError("command", "timeout", str(exc)) from exc
    if completed.returncode != 0:
        raise HermesInventoryError("command", "nonzero_exit", completed.stderr.strip() or completed.stdout.strip())
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise HermesInventoryError("command", "invalid_json", str(exc)) from exc


def read_hermes_http_sources(url: str, *, timeout: float = 10) -> dict:
    try:
        response = httpx.get(url, timeout=timeout)
    except httpx.HTTPError as exc:
        raise HermesInventoryError("http", "request_failed", str(exc)) from exc
    if response.status_code >= 400:
        raise HermesInventoryError("http", "http_error", str(response.status_code))
    try:
        return response.json()
    except json.JSONDecodeError as exc:
        raise HermesInventoryError("http", "invalid_json", str(exc)) from exc


def enumerate_live_profiles(home: str | Path) -> dict[str, list[dict[str, Any]]]:
    home = Path(home)
    profiles = []
    default_config = _read_yaml_file(home / "config.yaml")
    if default_config:
        profiles.append(_profile_record("default", home, default_config, is_default=True))

    profiles_dir = home / "profiles"
    if profiles_dir.is_dir():
        for profile_dir in sorted(path for path in profiles_dir.iterdir() if path.is_dir()):
            config = _read_yaml_file(profile_dir / "config.yaml")
            if config:
                profiles.append(_profile_record(profile_dir.name, profile_dir, config, is_default=False))
    return {"profiles": profiles}


def read_gateway_config(home: str | Path) -> dict[str, Any] | None:
    return _read_yaml_file(Path(home) / "config.yaml")


def _profile_record(name: str, path: Path, config: dict[str, Any], *, is_default: bool) -> dict[str, Any]:
    profile_info = {
        "name": name,
        "path": str(path),
        "is_default": is_default,
        "gateway_running": False,
        "provider": config.get("provider"),
    }
    slots = _profile_slots_from_config(profile_info, config)
    return {
        **profile_info,
        "main_combo": slots.main_combo,
        "auxiliary": slots.auxiliary,
    }


def _profile_slots_from_record(profile: dict[str, Any]) -> ProfileSlots:
    if "main_combo" in profile:
        return ProfileSlots(
            name=str(profile["name"]),
            path=str(profile.get("path", "")),
            gateway_running=bool(profile.get("gateway_running")),
            main_combo=profile.get("main_combo"),
            auxiliary=profile.get("auxiliary") or {},
        )
    return read_profile_slots(profile)


def _profile_slots_from_config(profile_info: dict[str, Any], config: dict[str, Any]) -> ProfileSlots:
    auxiliary = config.get("auxiliary") or {}
    if not isinstance(auxiliary, dict):
        raise HermesInventoryError("filesystem", "invalid_config", str(Path(profile_info["path"]) / "config.yaml"))
    return ProfileSlots(
        name=str(profile_info["name"]),
        path=str(profile_info["path"]),
        gateway_running=bool(profile_info.get("gateway_running")),
        main_combo=_main_combo_from_config(config.get("model")),
        auxiliary=auxiliary,
    )


def _main_combo_from_config(model: Any) -> str | None:
    if isinstance(model, dict):
        value = model.get("default")
        return str(value) if value else None
    if isinstance(model, str) and model:
        return model
    return None


def _read_yaml_file(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    data = yaml.safe_load(path.read_text()) or {}
    if not isinstance(data, dict):
        raise HermesInventoryError("filesystem", "invalid_config", str(path))
    return data
