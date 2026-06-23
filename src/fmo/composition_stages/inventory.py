from __future__ import annotations

from fmo.hermes_inventory import Inventory
from fmo.pipeline import PipelineContext, StageResult

from . import _legacy
from ._legacy import StageDependencies


def _hermes_inventory_stage(dependencies: StageDependencies, context: PipelineContext) -> StageResult:
    return _legacy._hermes_inventory_stage(dependencies, context)


def _read_hermes_inventory(dependencies: StageDependencies) -> Inventory:
    return _legacy._read_hermes_inventory(dependencies)


def _run_hermes_inspector(dependencies: StageDependencies, inventory: Inventory) -> None:
    _legacy._run_hermes_inspector(dependencies, inventory)
