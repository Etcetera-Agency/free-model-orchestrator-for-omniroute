import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
    payload = complete_with_adapter(
        call_instructor,
        site=LlmSiteConfig(
            name="hermes-inspector",
            model="omniroute/free-inspector",
            max_prompt_chars=6000,
        ),
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
# Shapes below mirror NousResearch/hermes-agent @ tag v2026.6.5 exactly:
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
        role = _combo_role(profile.get("model"))  # profile config model is the OmniRoute combo
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


def build_hermes_inventory(
    *,
    cron_jobs: Any = None,
    webhook_subscriptions: Any = None,
    profiles: Any = None,
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
    return Inventory(consumers=consumers)


def read_hermes_home(home: str | Path, *, profiles: Any = None) -> Inventory:
    """Read a real `HERMES_HOME` directory layout into an Inventory.

    Reads `cron/jobs.json` and `webhook_subscriptions.json`, and opens
    `state.db` read-only for observed demand. Profile enumeration is supplied by
    the caller (Hermes derives it from a CLI/HTTP listing, not a single file).
    """
    home = Path(home)
    jobs_file = home / "cron" / "jobs.json"
    subs_file = home / "webhook_subscriptions.json"
    state_db = home / "state.db"

    cron_jobs = json.loads(jobs_file.read_text()) if jobs_file.is_file() else None
    webhook_subscriptions = json.loads(subs_file.read_text()) if subs_file.is_file() else None

    connection = None
    if state_db.is_file():
        connection = sqlite3.connect(f"file:{state_db}?mode=ro", uri=True)
    try:
        return build_hermes_inventory(
            cron_jobs=cron_jobs,
            webhook_subscriptions=webhook_subscriptions,
            profiles=profiles,
            session_connection=connection,
        )
    finally:
        if connection is not None:
            connection.close()
