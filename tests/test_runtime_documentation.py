import importlib
import inspect
import pkgutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
# Active proposal slices awaiting TDD implementation. Each entry is dropped from
# tests/spec_coverage_pending.txt (and here) when its test lands. Slices are
# listed in openspec/TODO.md and openspec/changes/<id>/.
EXPECTED_ACTIVE_PENDING = {
    # refactor-split-stages-runtime
    "system-architecture::Probing, telemetry, inventory, and role stages live in dedicated modules",
    "system-architecture::Role scoring helpers move with the role stage",
    # refactor-split-stages-apply
    "system-architecture::Allocation, apply, rollback, and audit stages live in dedicated modules",
    "system-architecture::Shared stage helpers live in one helpers module",
    # refactor-extract-test-fakes
    "system-architecture::Test fakes live in a shared test-support module",
    "system-architecture::Composition tests mirror the stage packages",
    "system-architecture::Test suite runs from both pytest entry points",
    # refactor-unify-shared-helpers
    "system-architecture::Row access helpers are defined once in the persistence base",
    "system-architecture::Timestamp and hashing helpers are centralized",
}


@pytest.mark.spec("runtime-documentation::Active docs state")
@pytest.mark.spec("runtime-documentation::Runtime docs reflect validation and pending coverage")
@pytest.mark.spec("runtime-documentation::TODO does not contradict active work")
def test_runtime_docs_record_executable_scenario_policy_and_pending_allowlist():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    completion_review = (ROOT / "completion.review").read_text(encoding="utf-8")
    todo = (ROOT / "openspec" / "TODO.md").read_text(encoding="utf-8")
    pending_lines = [
        line.strip()
        for line in (ROOT / "tests" / "spec_coverage_pending.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]

    assert "Executable scenarios" in agents
    assert "@pytest.mark." + "spec(" in agents
    assert "<capability>::<Scenario name>" in agents
    assert set(pending_lines) == EXPECTED_ACTIVE_PENDING
    assert "repository methods" in completion_review
    assert "adapter-backed boundary" in completion_review
    assert "Deferred follow-up" in todo
    assert "/api/combos" in todo
    assert "Active Slice Backlog" not in todo
    assert "Active review follow-up slices" not in todo


@pytest.mark.spec("system-architecture::Stage domains live in separate modules")
@pytest.mark.spec("system-architecture::Refactor preserves behavior")
def test_composition_root_is_thin_and_stage_domains_are_split():
    root = (ROOT / "src" / "fmo" / "composition.py").read_text(encoding="utf-8")
    stages = (ROOT / "src" / "fmo" / "composition_stages" / "_legacy.py").read_text(encoding="utf-8")
    aa_index = (ROOT / "src" / "fmo" / "aa_index_runtime.py").read_text(encoding="utf-8")
    contracts = (ROOT / "src" / "fmo" / "composition_contracts.py").read_text(encoding="utf-8")

    assert root.count("\ndef ") <= 8
    assert "def _apply_stage" not in root
    assert "def _quota_research_stage" not in root
    assert "def _run_aa_index_command" not in root
    assert "class RuntimeCliResult" not in root
    assert "def _apply_stage" in stages
    assert "def _quota_research_stage" in stages
    assert "def _run_aa_index_command" in aa_index
    assert "class RuntimeCliResult" in contracts


@pytest.mark.spec("system-architecture::Stage package re-exports preserve composition wiring")
def test_composition_stage_package_preserves_front_stage_wiring():
    stages = importlib.import_module("fmo.composition_stages")

    adapters = stages._production_stage_adapters()
    for name in (
        "model-matching",
        "quota-research",
        "quota-sync",
        "access-classification",
    ):
        assert name in adapters
        assert callable(adapters[name])
    assert callable(stages._metadata_stage)
    assert callable(stages._free_candidate_stage)
    assert callable(stages._account_discovery_stage)


@pytest.mark.spec("system-architecture::Discovery, quota, and access stages live in dedicated modules")
def test_front_composition_stages_live_in_dedicated_modules():
    package = importlib.import_module("fmo.composition_stages")

    assert hasattr(package, "__path__")
    modules = {item.name for item in pkgutil.iter_modules(package.__path__)}
    assert {"discovery", "quota", "access"}.issubset(modules)

    discovery = importlib.import_module("fmo.composition_stages.discovery")
    quota = importlib.import_module("fmo.composition_stages.quota")
    access = importlib.import_module("fmo.composition_stages.access")

    assert inspect.getmodule(discovery._metadata_stage).__name__.endswith(".discovery")
    assert inspect.getmodule(discovery._free_candidate_stage).__name__.endswith(".discovery")
    assert inspect.getmodule(discovery._account_discovery_stage).__name__.endswith(".discovery")
    assert inspect.getmodule(discovery._model_matching_stage).__name__.endswith(".discovery")
    assert inspect.getmodule(quota._quota_research_stage).__name__.endswith(".quota")
    assert inspect.getmodule(quota._quota_sync_stage).__name__.endswith(".quota")
    assert inspect.getmodule(access._access_classification_stage).__name__.endswith(".access")
