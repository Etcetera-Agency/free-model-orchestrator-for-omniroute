import json
import sqlite3
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import yaml
from pydantic import BaseModel

from fmo.forecast import quality_band_for_demand
from fmo.idempotency import hash_parts
from fmo.llm_runtime import LlmSiteConfig, complete_with_adapter

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "reference" / "prompts"
HERMES_INSPECTOR_PROMPT = PROMPTS_DIR / "hermes-inspector.md"
HERMES_INTELLIGENCE_INSPECTOR_PROMPT = PROMPTS_DIR / "hermes-intelligence-inspector.md"


@dataclass(frozen=True)
class Consumer:
    role_id: str
    consumer_type: str
    consumer: str
    cadence: str
    calls_per_run: float
    describing_text: str = ""
    required_capabilities: tuple[str, ...] = ()
    minimum_context_window: int = 0


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
    intelligence_stale_units: tuple[str, ...] = ()

    def rebuild_combo(self, *, material_allocation_changed: bool) -> bool:
        return material_allocation_changed


@dataclass(frozen=True)
class InspectorForecast:
    role: str
    expected_calls: float
    average_input_tokens: float
    average_output_tokens: float
    confidence: str
    model_choice: dict[str, Any] | None = None
    quota_change: None = None


class InspectorForecastResponse(BaseModel):
    role: str
    expected_calls: float
    average_input_tokens: float
    average_output_tokens: float
    confidence: str


@dataclass(frozen=True)
class DescribingUnit:
    role_id: str
    consumer_type: str
    consumer: str
    unit_key: str
    text: str
    content_hash: str
    required_capabilities: tuple[str, ...] = ()
    minimum_context_window: int = 0


@dataclass(frozen=True)
class IntelligenceVerdict:
    capability_axis: str
    tier: str
    confidence: str
    anchor: float
    content_hash: str


@dataclass(frozen=True)
class RoleQualityAnchor:
    role_id: str
    capability_axis: str
    tier: str
    anchor: float
    confidence: str
    source: str
    content_hashes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ComboGridCell:
    combo_id: str
    capability_axis: str
    tier: str
    anchor: float
    required_capabilities: tuple[str, ...] = ()
    minimum_context_window: int = 0
    auxiliary: bool = False
    reusable: bool = True


class IntelligenceForecastResponse(BaseModel):
    capability_axis: str
    tier: str
    confidence: str


QUALITY_AXES = {"intelligence_index", "coding_index", "agentic_index"}
QUALITY_TIERS = {"low": 20.0, "medium": 50.0, "high": 80.0}
ADEQUACY_FLOOR = 20.0


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


def inventory_diff(old: Inventory, new: Inventory) -> InventoryDiff:
    old_set = {
        (consumer.role_id, consumer.consumer_type, consumer.consumer, consumer.cadence, consumer.calls_per_run)
        for consumer in old.consumers
    }
    new_set = {
        (consumer.role_id, consumer.consumer_type, consumer.consumer, consumer.cadence, consumer.calls_per_run)
        for consumer in new.consumers
    }
    old_intelligence = {describing_unit_key(consumer): describing_unit_hash(consumer) for consumer in old.consumers}
    new_intelligence = {describing_unit_key(consumer): describing_unit_hash(consumer) for consumer in new.consumers}
    intelligence_changed = tuple(
        sorted(key for key, value in new_intelligence.items() if old_intelligence.get(key) != value)
    )
    changed = old_set != new_set
    return InventoryDiff(
        forecast_stale=changed,
        run_inspector=changed,
        intelligence_stale_units=intelligence_changed,
    )


def assemble_inspector_prompt(inventory: Inventory, *, changes: list[str], secrets: dict[str, str]) -> str:
    lines = ["Hermes inventory forecast request", "Changes:", *changes, "Consumers:"]
    for consumer in inventory.consumers:
        lines.append(
            f"{consumer.role_id} {consumer.consumer_type} {consumer.consumer} {consumer.cadence} {consumer.calls_per_run}"
        )
    prompt = "\n".join(lines)
    for secret in secrets.values():
        prompt = prompt.replace(secret, "[REDACTED]")
    return prompt


def run_inspector(call_instructor, prompt: str) -> InspectorForecast:
    site = LlmSiteConfig(
        name="hermes-inspector",
        prompt_path=HERMES_INSPECTOR_PROMPT,
        max_prompt_chars=6000,
    )
    if hasattr(call_instructor, "complete"):
        payload = call_instructor.complete(
            site=site, context={"prompt": prompt}, response_model=InspectorForecastResponse
        )
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


def describing_unit_key(consumer: Consumer) -> str:
    return f"{consumer.role_id}:{consumer.consumer_type}:{consumer.consumer}"


def describing_unit_hash(consumer: Consumer) -> str:
    return hash_parts(consumer.consumer_type, consumer.consumer, consumer.describing_text)


def describing_units(inventory: Inventory) -> list[DescribingUnit]:
    units = []
    for consumer in inventory.consumers:
        text = consumer.describing_text.strip()
        if not text:
            continue
        units.append(
            DescribingUnit(
                role_id=consumer.role_id,
                consumer_type=consumer.consumer_type,
                consumer=consumer.consumer,
                unit_key=describing_unit_key(consumer),
                text=text,
                content_hash=describing_unit_hash(consumer),
                required_capabilities=tuple(sorted(consumer.required_capabilities)),
                minimum_context_window=consumer.minimum_context_window,
            )
        )
    return units


def assemble_intelligence_prompt(
    unit: DescribingUnit, *, secrets: dict[str, str], max_prompt_chars: int = 12000
) -> str:
    prompt = "\n".join(
        [
            "Hermes intelligence anchor request",
            f"Role: {unit.role_id}",
            f"Consumer type: {unit.consumer_type}",
            f"Consumer: {unit.consumer}",
            f"Required capabilities: {', '.join(unit.required_capabilities) or 'none'}",
            f"Minimum context window: {unit.minimum_context_window}",
            "Task description:",
            unit.text,
        ]
    )
    for secret in secrets.values():
        prompt = prompt.replace(secret, "[REDACTED]")
    return prompt[:max_prompt_chars]


def run_intelligence_inspector(call_instructor, prompt: str) -> IntelligenceForecastResponse:
    site = LlmSiteConfig(
        name="hermes-intelligence-inspector",
        prompt_path=HERMES_INTELLIGENCE_INSPECTOR_PROMPT,
        max_prompt_chars=12000,
        advisory=True,
    )
    if hasattr(call_instructor, "complete"):
        return call_instructor.complete(
            site=site, context={"prompt": prompt}, response_model=IntelligenceForecastResponse
        )
    return complete_with_adapter(
        call_instructor,
        site=site,
        context={"prompt": prompt},
        response_model=IntelligenceForecastResponse,
    )


def tier_to_anchor(tier: str) -> float:
    return QUALITY_TIERS.get(tier.lower(), QUALITY_TIERS["medium"])


# AICODE-NOTE: Intelligence refresh is content-hash driven; schedule/demand
# changes may refresh demand forecasts without re-sending unchanged descriptions.
def role_quality_anchors(
    inventory: Inventory,
    call_instructor,
    *,
    cache: dict[str, IntelligenceVerdict] | None = None,
    seed_anchors: dict[str, RoleQualityAnchor] | None = None,
    adequacy_floor: float = ADEQUACY_FLOOR,
    secrets: dict[str, str] | None = None,
) -> dict[str, RoleQualityAnchor]:
    cache = cache if cache is not None else {}
    seed_anchors = seed_anchors or {}
    secrets = secrets or {}
    units_by_role: dict[str, list[DescribingUnit]] = {}
    for unit in describing_units(inventory):
        units_by_role.setdefault(unit.role_id, []).append(unit)

    anchors: dict[str, RoleQualityAnchor] = {}
    for consumer in inventory.consumers:
        anchors.setdefault(
            consumer.role_id,
            RoleQualityAnchor(
                role_id=consumer.role_id,
                capability_axis="intelligence_index",
                tier="low",
                anchor=adequacy_floor,
                confidence="floor",
                source="adequacy_floor",
            ),
        )

    for role_id, units in units_by_role.items():
        verdicts = []
        try:
            for unit in units:
                cached = cache.get(unit.unit_key)
                if cached is not None and cached.content_hash == unit.content_hash:
                    verdicts.append(cached)
                    continue
                payload = run_intelligence_inspector(
                    call_instructor,
                    assemble_intelligence_prompt(unit, secrets=secrets),
                )
                axis = payload.capability_axis if payload.capability_axis in QUALITY_AXES else "intelligence_index"
                tier = payload.tier.lower() if payload.tier.lower() in QUALITY_TIERS else "medium"
                verdict = IntelligenceVerdict(
                    capability_axis=axis,
                    tier=tier,
                    confidence=payload.confidence,
                    anchor=tier_to_anchor(tier),
                    content_hash=unit.content_hash,
                )
                cache[unit.unit_key] = verdict
                verdicts.append(verdict)
        except Exception:
            anchors[role_id] = seed_anchors.get(role_id) or anchors[role_id]
            continue
        winner = max(verdicts, key=lambda verdict: verdict.anchor)
        anchors[role_id] = RoleQualityAnchor(
            role_id=role_id,
            capability_axis=winner.capability_axis,
            tier=winner.tier,
            anchor=winner.anchor,
            confidence=winner.confidence,
            source="intelligence_inspector",
            content_hashes=tuple(unit.content_hash for unit in units),
        )
    return anchors


def forecast_with_quality_choice(forecast: InspectorForecast, anchor: RoleQualityAnchor) -> InspectorForecast:
    return InspectorForecast(
        role=forecast.role,
        expected_calls=forecast.expected_calls,
        average_input_tokens=forecast.average_input_tokens,
        average_output_tokens=forecast.average_output_tokens,
        confidence=forecast.confidence,
        model_choice={
            "axis": anchor.capability_axis,
            "tier": anchor.tier,
            "anchor": anchor.anchor,
        },
    )


def quality_band_for_anchor(
    anchor: RoleQualityAnchor,
    *,
    candidates: list[dict[str, Any]],
    protected_requests: float,
    adequacy_floor: float = ADEQUACY_FLOOR,
):
    return quality_band_for_demand(
        anchor=anchor.anchor,
        candidates=candidates,
        protected_requests=protected_requests,
        adequacy_floor=adequacy_floor,
    )


def select_combo_grid_cell(
    *,
    role_id: str,
    capability_axis: str,
    tier: str,
    required_capabilities: set[str],
    minimum_context_window: int,
    grid: list[ComboGridCell],
    auxiliary: bool = False,
) -> ComboGridCell:
    candidates = [
        cell
        for cell in grid
        if cell.auxiliary == auxiliary
        and cell.capability_axis == capability_axis
        and cell.tier == tier
        and required_capabilities.issubset(set(cell.required_capabilities))
        and cell.minimum_context_window >= minimum_context_window
        and cell.reusable
    ]
    if candidates:
        return sorted(candidates, key=lambda cell: (cell.anchor, cell.combo_id))[0]
    prefix = "aux" if auxiliary else "role"
    return ComboGridCell(
        combo_id=f"fmo-unique-{prefix}-{role_id}",
        capability_axis=capability_axis,
        tier=tier,
        anchor=tier_to_anchor(tier),
        required_capabilities=tuple(sorted(required_capabilities)),
        minimum_context_window=minimum_context_window,
        auxiliary=auxiliary,
        reusable=False,
    )


def demand_driven_combo_profiles(
    inventory: Inventory,
    anchors: dict[str, RoleQualityAnchor],
) -> set[tuple[str, str, tuple[str, ...], int, bool]]:
    profiles: set[tuple[str, str, tuple[str, ...], int, bool]] = set()
    for consumer in inventory.consumers:
        anchor = anchors.get(consumer.role_id)
        axis = anchor.capability_axis if anchor is not None else "intelligence_index"
        tier = anchor.tier if anchor is not None else "low"
        profiles.add(
            (
                axis,
                tier,
                tuple(sorted(consumer.required_capabilities)),
                int(consumer.minimum_context_window),
                consumer.consumer_type == "auxiliary",
            )
        )
    return profiles


def bootstrap_combo_payload(cell: ComboGridCell, *, seed_model: str, provider_id: str) -> dict[str, Any]:
    return {
        "name": cell.combo_id,
        "models": [{"kind": "model", "model": seed_model, "providerId": provider_id, "weight": 0}],
        "strategy": "priority",
    }


def anchor_after_rebalance_event(anchor: RoleQualityAnchor, *, persona_hash_changed: bool) -> RoleQualityAnchor | None:
    return None if persona_hash_changed else anchor


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
    if not _table_exists(connection, "sessions"):
        return {}
    cursor = connection.execute(
        "SELECT model, AVG(api_call_count) FROM sessions WHERE model IS NOT NULL AND api_call_count > 0 GROUP BY model"
    )
    return {row[0]: float(row[1]) for row in cursor.fetchall() if row[0]}


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    cursor = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ? LIMIT 1",
        (table,),
    )
    return cursor.fetchone() is not None


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
                describing_text=str(job.get("prompt") or job.get("description") or ""),
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
        is_service = bool(profile.get("gateway_running"))
        if slots.main_combo is not None:
            role = _combo_role(slots.main_combo)
            consumers.append(
                Consumer(
                    role_id=role,
                    consumer_type="service" if is_service else "agent_profile",
                    consumer=profile["name"],
                    cadence="continuous" if is_service else "manual",
                    calls_per_run=demand_by_role.get(role, BOOTSTRAP_CALLS_PER_RUN),
                    describing_text=_profile_describing_text(slots.path, slots.auxiliary),
                )
            )
        consumers.extend(
            _auxiliary_consumers(
                owner=profile["name"],
                main_combo=slots.main_combo,
                auxiliary=slots.auxiliary,
                demand_by_role=demand_by_role,
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
    gateway_auxiliary = _auxiliary_mapping(config.get("auxiliary"))
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
                describing_text=str(platform.get("description") or platform.get("prompt") or ""),
            )
        )
        auxiliary = {**gateway_auxiliary, **_auxiliary_mapping(platform.get("auxiliary"))}
        consumers.extend(
            _auxiliary_consumers(
                owner=f"gateway:{name}",
                main_combo=role,
                auxiliary=auxiliary,
                demand_by_role=demand_by_role,
            )
        )
    return consumers


def _auxiliary_consumers(
    *,
    owner: str,
    main_combo: str | None,
    auxiliary: dict[str, Any],
    demand_by_role: dict[str, float],
) -> list[Consumer]:
    consumers = []
    for slot, config in sorted(auxiliary.items()):
        combo = _resolved_aux_combo(config, main_combo)
        if combo is None:
            continue
        role = _combo_role(combo)
        consumers.append(
            Consumer(
                role_id=role,
                consumer_type="auxiliary",
                consumer=f"{owner}:{slot}",
                cadence="auxiliary",
                calls_per_run=demand_by_role.get(role, BOOTSTRAP_CALLS_PER_RUN),
                describing_text=_auxiliary_purpose(slot, config),
                required_capabilities=_auxiliary_capabilities(slot, config),
            )
        )
    return consumers


def _resolved_aux_combo(config: Any, main_combo: str | None) -> str | None:
    if not isinstance(config, dict):
        return None
    if str(config.get("provider") or "").lower() == "auto":
        return None
    model = config.get("model")
    if not model or model == main_combo:
        return None
    return str(model)


def _auxiliary_mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _profile_describing_text(path: str, auxiliary: dict[str, Any]) -> str:
    profile_dir = Path(path)
    parts = []
    for filename in ("SOUL.md", "AGENTS.md"):
        file = profile_dir / filename
        if file.is_file():
            parts.append(f"{filename}:\n{file.read_text(encoding='utf-8')}")
    allowed_tools = auxiliary.get("allowed_tools") if isinstance(auxiliary, dict) else None
    if allowed_tools:
        parts.append(f"allowed_tools: {json.dumps(allowed_tools, sort_keys=True)}")
    return "\n\n".join(parts)


def _auxiliary_purpose(slot: str, config: Any) -> str:
    if not isinstance(config, dict):
        return ""
    purpose = config.get("purpose") or config.get("description") or config.get("capability") or slot
    return str(purpose)


def _auxiliary_capabilities(slot: str, config: Any) -> tuple[str, ...]:
    if not isinstance(config, dict):
        return ()
    raw = config.get("required_capabilities") or config.get("capabilities") or config.get("capability")
    if isinstance(raw, str):
        values = [raw]
    elif isinstance(raw, list | tuple | set):
        values = [str(item) for item in raw]
    else:
        values = []
    lowered = {value.lower() for value in values}
    slot_name = slot.lower()
    if "vision" in lowered or "vision" in slot_name or "image" in slot_name:
        lowered.add("vision")
    if "tool_calling" in lowered or "tools" in slot_name or "mcp" in slot_name or "skills" in slot_name:
        lowered.add("tool_calling")
    if "structured_output" in lowered or "approval" in slot_name or "structured" in slot_name:
        lowered.add("structured_output")
    return tuple(sorted(lowered))


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
