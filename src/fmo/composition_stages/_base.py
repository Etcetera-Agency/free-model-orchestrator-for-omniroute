from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from fmo.accounts import discover_live_accounts
from fmo.config import StartupConfig
from fmo.hermes_inventory import Inventory
from fmo.llm_runtime import SharedInstructorRuntime
from fmo.metadata_sync import MetadataSyncResult
from fmo.omniroute import OmniRouteClient
from fmo.persistence import Repository
from fmo.pipeline import PipelineContext, StageResult
from fmo.registry import FreeRegistrySyncOutcome, sync_live_free_registry
from fmo.scanner import CatalogScanner

MetadataSync = Callable[..., MetadataSyncResult]
RegistrySync = Callable[[Any], FreeRegistrySyncOutcome]
CatalogScan = Callable[[CatalogScanner, Any, str], object]
LiveCatalogRefresh = Callable[[Repository, Any, str], object]
AccountDiscovery = Callable[..., object]
StageAdapter = Callable[["StageDependencies", PipelineContext], StageResult]
HermesInventoryAdapter = Callable[[StartupConfig], Inventory]


def _default_catalog_scan() -> CatalogScan:
    from .discovery import _scan_catalogs

    return _scan_catalogs


def _default_live_catalog_refresh() -> LiveCatalogRefresh:
    from .discovery import _refresh_live_catalog

    return _refresh_live_catalog


def _noop_live_catalog_refresh() -> LiveCatalogRefresh:
    return lambda _repository, _client, _omniroute_instance_id: {}


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
    registry_sync: RegistrySync = sync_live_free_registry
    catalog_scan: CatalogScan = field(default_factory=_default_catalog_scan)
    live_catalog_refresh: LiveCatalogRefresh = field(default_factory=_noop_live_catalog_refresh)
    account_discovery: AccountDiscovery = discover_live_accounts
    stage_adapters: dict[str, StageAdapter] = field(default_factory=_default_stage_adapters)
    hermes_inventory: HermesInventoryAdapter | None = None
    instructor_from_openai: Any | None = None
    openai_client_factory: Any | None = None


@dataclass(frozen=True)
class FreeModelChanges:
    gained: set[tuple[str, str]]
    lost: set[tuple[str, str]]
    known: bool = True

    @property
    def triggered(self) -> bool:
        return not self.known or bool(self.gained or self.lost)


def _production_stage_adapters() -> dict[str, StageAdapter]:
    from .access import _access_classification_stage
    from .allocation import _allocation_stage, _demand_forecast_stage
    from .apply import _apply_stage, _diff_stage
    from .audit import _audit_stage
    from .discovery import _model_matching_stage
    from .inventory import _hermes_inventory_stage
    from .probing import _probing_stage
    from .roles import _role_lifecycle_stage, _role_scoring_stage
    from .telemetry import _telemetry_sync_stage

    return {
        "model-matching": _model_matching_stage,
        "access-classification": _access_classification_stage,
        "probing": _probing_stage,
        "telemetry-sync": _telemetry_sync_stage,
        "hermes-inventory": _hermes_inventory_stage,
        "role-lifecycle": _role_lifecycle_stage,
        "role-scoring": _role_scoring_stage,
        "demand-forecast": _demand_forecast_stage,
        "allocation": _allocation_stage,
        "diff": _diff_stage,
        "apply": _apply_stage,
        "audit": _audit_stage,
    }
