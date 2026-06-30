import ast
import importlib
import inspect
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

EXPECTED_ACTIVE_PENDING = {
    "data-model::Auxiliary consumer type persists",
    "data-model::Migration keeps existing databases compatible",
    "demand-forecast::Bursty weekly load",
    "demand-forecast::Cold start floor applied",
    "demand-forecast::Demand comes from the forecast",
    "demand-forecast::Dependency cycle",
    "demand-forecast::Multiple agents and a shared role",
    "demand-forecast::Reserve applied once",
    "demand-forecast::Unknown new role",
    "hermes-inventory::Inspector uses resolver-selected provider model",
    "hermes-inventory::Resolver-less inspector fails closed",
    "llm-runtime::Add or change runtime defaults",
    "llm-runtime::Advisory site fails open",
    "llm-runtime::All sites use the adapter",
    "llm-runtime::Inspector sites fail closed without a resolver model",
    "llm-runtime::Inspector sites use one resolver approach",
    "llm-runtime::Malformed completion repaired or rejected",
    "omniroute-client::Bridge denies combo test helper",
    "persistence::Re-run refreshes current combo snapshot recency",
    "pipeline-orchestration::Audit persists records",
    "system-architecture::Intraday failure not rebuilt",
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
    assert "Removed FMO matching/probing ownership" in completion_review
    assert "Deferred follow-up" in todo
    assert "fmo-pools/v1" in todo


@pytest.mark.spec("system-architecture::Stage domains live in separate modules")
@pytest.mark.spec("system-architecture::Refactor preserves behavior")
@pytest.mark.spec("system-architecture::No legacy delegation module remains")
def test_composition_root_is_thin_and_stage_domains_are_current():
    root = (ROOT / "src" / "fmo" / "composition.py").read_text(encoding="utf-8")
    stages_dir = ROOT / "src" / "fmo" / "composition_stages"
    stage_sources = {
        path.name: path.read_text(encoding="utf-8") for path in stages_dir.glob("*.py") if path.name != "__init__.py"
    }

    assert "_legacy.py" not in stage_sources
    assert all("_legacy" not in source for source in stage_sources.values())
    assert root.count("\ndef ") <= 13
    assert "def _refresh_live_catalog" not in root
    assert "def sweep_provider_models" not in root
    assert "def _run_aa_index_command" not in root
    assert "access.py" not in stage_sources
    assert "discovery.py" not in stage_sources
    assert "probing.py" not in stage_sources
    assert "telemetry.py" not in stage_sources


@pytest.mark.spec("system-architecture::Stage package re-exports preserve composition wiring")
def test_composition_stage_package_preserves_current_stage_wiring():
    stages = importlib.import_module("fmo.composition_stages")

    adapters = stages._production_stage_adapters()
    assert set(adapters) == {"hermes-inventory", "role-lifecycle", "demand-forecast", "audit"}
    assert callable(stages._hermes_inventory_stage)
    assert callable(stages._role_lifecycle_stage)
    assert callable(stages._demand_forecast_stage)
    assert callable(stages._audit_stage)


@pytest.mark.spec("system-architecture::Shared stage helpers live in one helpers module")
def test_shared_stage_helpers_live_in_helpers_module():
    helpers = importlib.import_module("fmo.composition_stages._helpers")

    for helper in ("_effect_result", "_adapter_stage", "_omniroute_instance_id"):
        assert inspect.getmodule(getattr(helpers, helper)).__name__.endswith("._helpers")


@pytest.mark.spec("system-architecture::Row access helpers are defined once in the persistence base")
def test_row_access_helpers_have_one_persistence_definition():
    helper_names = {"_one", "_optional", "_many", "_jsonb", "_content_hash"}
    definitions: dict[str, list[Path]] = {name: [] for name in helper_names}

    for path in (ROOT / "src" / "fmo").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name in helper_names:
                definitions[node.name].append(path.relative_to(ROOT))

    assert definitions == {name: [Path("src/fmo/persistence/_base.py")] for name in helper_names}


@pytest.mark.spec("system-architecture::Test suite runs from both pytest entry points")
def test_pytest_entry_points_have_shared_import_path():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    tests_package = ROOT / "tests" / "__init__.py"

    assert tests_package.exists()
    assert 'pythonpath = ["src", ".", "tests"]' in pyproject
    assert "$(VENV)/pytest -q" in makefile
