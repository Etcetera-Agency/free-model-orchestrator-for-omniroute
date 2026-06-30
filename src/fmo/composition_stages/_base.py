from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from fmo.config import StartupConfig
from fmo.hermes_inventory import Inventory
from fmo.llm_runtime import SharedInstructorRuntime
from fmo.omniroute import OmniRouteClient
from fmo.persistence import Repository
from fmo.pipeline import PipelineContext, StageResult

StageAdapter = Callable[["StageDependencies", PipelineContext], StageResult]
HermesInventoryAdapter = Callable[[StartupConfig], Inventory]


def _default_stage_adapters() -> dict[str, StageAdapter]:
    return _production_stage_adapters()


@dataclass(frozen=True)
class StageDependencies:
    repository: Repository | None
    omniroute_client: OmniRouteClient | None
    config: StartupConfig | None = None
    llm_runtime: SharedInstructorRuntime | None = None
    hermes_inventory_adapter: HermesInventoryAdapter | None = None


@dataclass(frozen=True)
class StageAdapters:
    stage_adapters: dict[str, StageAdapter] = field(default_factory=_default_stage_adapters)
    hermes_inventory: HermesInventoryAdapter | None = None


def _production_stage_adapters() -> dict[str, StageAdapter]:
    from .audit import _audit_stage
    from .demand import _demand_forecast_stage
    from .inventory import _hermes_inventory_stage
    from .roles import _role_lifecycle_stage

    return {
        "hermes-inventory": _hermes_inventory_stage,
        "role-lifecycle": _role_lifecycle_stage,
        "demand-forecast": _demand_forecast_stage,
        "audit": _audit_stage,
    }
