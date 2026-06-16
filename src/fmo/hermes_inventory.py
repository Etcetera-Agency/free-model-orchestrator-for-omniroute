from dataclasses import dataclass


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
    payload = call_instructor(prompt)
    return InspectorForecast(
        role=payload["role"],
        expected_calls=payload["expected_calls"],
        average_input_tokens=payload["average_input_tokens"],
        average_output_tokens=payload["average_output_tokens"],
        confidence=payload["confidence"],
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
