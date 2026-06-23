from __future__ import annotations

from collections.abc import Callable

from fmo.pipeline import PipelineContext, StageResult
from fmo.scanner import CatalogScanner

from . import _legacy
from ._legacy import StageAdapters, StageDependencies


def _metadata_stage(sync: _legacy.MetadataSync) -> Callable[[PipelineContext], StageResult]:
    return _legacy._metadata_stage(sync)


def _free_candidate_stage(
    dependencies: StageDependencies, adapters: StageAdapters
) -> Callable[[PipelineContext], StageResult]:
    return _legacy._free_candidate_stage(dependencies, adapters)


def _account_discovery_stage(
    dependencies: StageDependencies, adapters: StageAdapters
) -> Callable[[PipelineContext], StageResult]:
    return _legacy._account_discovery_stage(dependencies, adapters)


def _model_matching_stage(dependencies: StageDependencies, context: PipelineContext) -> StageResult:
    return _legacy._model_matching_stage(dependencies, context)


def _scan_catalogs(scanner: CatalogScanner, client: object, omniroute_instance_id: str) -> object:
    return _legacy._scan_catalogs(scanner, client, omniroute_instance_id)
