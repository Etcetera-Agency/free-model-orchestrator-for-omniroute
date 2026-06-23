from __future__ import annotations

from pathlib import Path

from fmo.hermes_inventory import (
    HermesInventoryError,
    Inventory,
    assemble_inspector_prompt,
    build_hermes_inventory,
    forecast_with_quality_choice,
    read_hermes_command_sources,
    read_hermes_home,
    read_hermes_http_sources,
    role_quality_anchors,
    run_inspector,
)
from fmo.idempotency import hash_parts
from fmo.pipeline import PipelineContext, StageResult

from ._base import StageDependencies
from ._helpers import _effect_result


def _hermes_inventory_stage(dependencies: StageDependencies, context: PipelineContext) -> StageResult:
    if dependencies.config is None:
        return StageResult(status="validation_failed", reason="startup_config_required")
    try:
        inventory = _read_hermes_inventory(dependencies)
    except (ValueError, HermesInventoryError) as exc:
        return StageResult(status="validation_failed", reason=str(exc))
    source_hash = hash_parts(
        dependencies.config.hermes_inventory_mode,
        *[
            hash_parts(
                consumer.role_id,
                consumer.consumer_type,
                consumer.consumer,
                consumer.cadence,
                str(consumer.calls_per_run),
            )
            for consumer in inventory.consumers
        ],
    )
    forecast = _run_hermes_inspector(dependencies, inventory)
    quality_anchors = role_quality_anchors(inventory, dependencies.llm_runtime)
    by_role: dict[str, float] = {}
    requirements_by_role: dict[str, dict] = {}
    for consumer in inventory.consumers:
        by_role[consumer.role_id] = by_role.get(consumer.role_id, 0.0) + float(consumer.calls_per_run)
        requirements = requirements_by_role.setdefault(
            consumer.role_id,
            {"capabilities": [], "minimum_context_window": 0},
        )
        requirements["capabilities"] = sorted(set(requirements["capabilities"]) | set(consumer.required_capabilities))
        requirements["minimum_context_window"] = max(
            int(requirements["minimum_context_window"]),
            int(consumer.minimum_context_window),
        )
    if forecast is not None:
        if forecast.role in quality_anchors:
            forecast = forecast_with_quality_choice(forecast, quality_anchors[forecast.role])
        by_role[forecast.role] = max(by_role.get(forecast.role, 0.0), float(forecast.expected_calls))
    with context.repository.database.transaction() as transaction:
        inventory_run = context.repository.role_consumers.start_inventory_run(
            transaction,
            source_mode=dependencies.config.hermes_inventory_mode,
            trigger_type="manual" if context.config.get("command") == "sync-hermes-inventory" else "daily",
            source_hash=source_hash,
        )
        for role_id, calls in by_role.items():
            quality_anchor = quality_anchors.get(role_id)
            requirements = requirements_by_role.get(role_id, {"capabilities": [], "minimum_context_window": 0})
            if quality_anchor is not None:
                requirements = {
                    **requirements,
                    "quality_anchor": {
                        "axis": quality_anchor.capability_axis,
                        "tier": quality_anchor.tier,
                        "anchor": quality_anchor.anchor,
                        "confidence": quality_anchor.confidence,
                        "source": quality_anchor.source,
                        "content_hashes": list(quality_anchor.content_hashes),
                    },
                }
            existing_role = transaction.execute(
                "SELECT 1 FROM roles WHERE id = %(role_id)s",
                {"role_id": role_id},
            ).fetchone()
            context.repository.roles.upsert(
                transaction,
                role_id=role_id,
                requirements=requirements,
                expected_load={"requests": calls},
                criticality=1,
                minimum_quality_metric=quality_anchor.capability_axis if quality_anchor is not None else None,
                minimum_quality_value=quality_anchor.anchor if quality_anchor is not None else None,
                maximum_quality_metric=quality_anchor.capability_axis if quality_anchor is not None else None,
                maximum_quality_value=quality_anchor.anchor if quality_anchor is not None else None,
                quality_gate_index_version="intelligence-inspector-v1" if quality_anchor is not None else None,
            )
            if existing_role is None:
                transaction.execute(
                    """
                    UPDATE roles
                    SET role_lifecycle_status = 'bootstrap_pending'
                    WHERE id = %(role_id)s
                    """,
                    {"role_id": role_id},
                )
        for consumer in inventory.consumers:
            context.repository.role_consumers.upsert(
                transaction,
                role_id=consumer.role_id,
                consumer_type=consumer.consumer_type,
                consumer_key=consumer.consumer,
                cadence=consumer.cadence,
                calls_per_run=consumer.calls_per_run,
                source_hash=source_hash,
            )
        context.repository.role_consumers.complete_inventory_run(
            transaction,
            run_id=inventory_run["id"],
            roles_found=len(by_role),
            consumers_found=len(inventory.consumers),
        )
    if not inventory.consumers:
        return StageResult(status="partial_stale", reason="hermes_inventory_empty")
    return _effect_result("hermes-inventory", changed=True)


def _read_hermes_inventory(dependencies: StageDependencies) -> Inventory:
    if dependencies.config is None:
        raise ValueError("startup_config_required")
    mode = dependencies.config.hermes_inventory_mode
    if dependencies.hermes_inventory_adapter is not None:
        return dependencies.hermes_inventory_adapter(dependencies.config)
    if mode == "filesystem":
        if not dependencies.config.hermes_home:
            raise ValueError("HERMES_HOME is required")
        return read_hermes_home(Path(dependencies.config.hermes_home or ""))
    if mode == "command":
        if not dependencies.config.hermes_inventory_command:
            raise ValueError("HERMES_INVENTORY_COMMAND is required")
        sources = read_hermes_command_sources(str(dependencies.config.hermes_inventory_command or "").split())
        return build_hermes_inventory(**sources)
    if mode == "http":
        if not dependencies.config.hermes_inventory_url:
            raise ValueError("HERMES_INVENTORY_URL is required")
        sources = read_hermes_http_sources(str(dependencies.config.hermes_inventory_url or ""))
        return build_hermes_inventory(**sources)
    raise ValueError("HERMES_INVENTORY_MODE is invalid")


def _run_hermes_inspector(dependencies: StageDependencies, inventory):
    if dependencies.llm_runtime is None:
        return None
    prompt = assemble_inspector_prompt(inventory, changes=[], secrets={})
    try:
        return run_inspector(dependencies.llm_runtime, prompt)
    except Exception:
        return None
