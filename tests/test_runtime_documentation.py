import ast
import importlib
import inspect
import pkgutil
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
# Active proposal slices awaiting TDD implementation. Each entry is dropped from
# tests/spec_coverage_pending.txt (and here) when its test lands. Slices are
# listed in openspec/TODO.md and openspec/changes/<id>/.
EXPECTED_ACTIVE_PENDING = {
    "aa-index-migration::Prompt is not selected-model JSON",
    "access-classifier::Empty evidence",
    "access-classifier::Exhausted by safety buffer",
    "access-classifier::Live API overrides models.dev",
    "access-classifier::Manual deny beats zero price",
    "access-classifier::Missing endpoint-local free evidence fails closed",
    "access-classifier::Missing quota precondition",
    "access-classifier::Promotion expired",
    "access-classifier::Local wildcard quota rules are ignored",
    "access-classifier::Removed beats zero price",
    "combo-applier::Smoke pass derived from non-empty SSE text",
    "data-model::Auxiliary consumer type persists",
    "data-model::Migration keeps existing databases compatible",
    "hermes-inventory::Inspector uses resolver-selected provider model",
    "hermes-inventory::Resolver-less inspector fails closed",
    "llm-runtime::AA migration prompt is loaded from file",
    "llm-runtime::Add or change runtime defaults",
    "llm-runtime::Advisory site fails open",
    "llm-runtime::All sites use the adapter",
    "llm-runtime::Inspector sites fail closed without a resolver model",
    "llm-runtime::Inspector sites use one resolver approach",
    "llm-runtime::Malformed completion repaired or rejected",
    "persistence::Re-run refreshes current combo snapshot recency",
    "pipeline-orchestration::Access classification persists status",
    "pipeline-orchestration::Command refreshes live catalog first",
    "pipeline-orchestration::External payload missing fails closed",
    "pipeline-orchestration::Scheduled run refreshes live catalog first",
    "probe-runner::Batch failures are persisted fail-closed",
    "probe-runner::No reserved capacity",
    "probe-runner::Non-200 or empty content",
    "provider-scanner::Absent provider is disabled before use",
    "provider-scanner::Disabled provider is tombstoned before use",
    "provider-scanner::Reappearing model clears tombstone",
    "role-scorer::Scoring semantics changed",
    "smart-combo-reviewer::Reviewer uses external prompt file",
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
    assert "repository methods" in completion_review
    assert "adapter-backed boundary" in completion_review
    assert "Deferred follow-up" in todo
    assert "/api/combos" in todo
    assert "Active Slice Backlog" not in todo
    assert "Active review follow-up slices" not in todo


@pytest.mark.spec("system-architecture::Stage domains live in separate modules")
@pytest.mark.spec("system-architecture::Refactor preserves behavior")
@pytest.mark.spec("system-architecture::No legacy delegation module remains")
def test_composition_root_is_thin_and_stage_domains_are_split():
    root = (ROOT / "src" / "fmo" / "composition.py").read_text(encoding="utf-8")
    stages_dir = ROOT / "src" / "fmo" / "composition_stages"
    stage_sources = {
        path.name: path.read_text(encoding="utf-8") for path in stages_dir.glob("*.py") if path.name != "__init__.py"
    }
    aa_index = (ROOT / "src" / "fmo" / "aa_index_runtime.py").read_text(encoding="utf-8")
    contracts = (ROOT / "src" / "fmo" / "composition_contracts.py").read_text(encoding="utf-8")

    assert "_legacy.py" not in stage_sources
    assert all("_legacy" not in source for source in stage_sources.values())
    assert root.count("\ndef ") <= 13
    assert "def _apply_stage" not in root
    assert "def _quota_research_stage" not in root
    assert "def _run_aa_index_command" not in root
    assert "class RuntimeCliResult" not in root
    assert "def _apply_stage" in stage_sources["apply.py"]
    assert "quota.py" not in stage_sources
    assert "def _run_aa_index_command" in aa_index
    assert "class RuntimeCliResult" in contracts


@pytest.mark.spec("system-architecture::Stage package re-exports preserve composition wiring")
def test_composition_stage_package_preserves_front_stage_wiring():
    stages = importlib.import_module("fmo.composition_stages")

    adapters = stages._production_stage_adapters()
    for name in (
        "model-matching",
        "access-classification",
    ):
        assert name in adapters
        assert callable(adapters[name])
    assert callable(stages._metadata_stage)
    assert callable(stages._free_candidate_stage)
    assert callable(stages._account_discovery_stage)


@pytest.mark.spec("system-architecture::Discovery and access stages live in dedicated modules")
@pytest.mark.spec("system-architecture::Front-of-pipeline stages are defined in their own modules")
def test_front_composition_stages_live_in_dedicated_modules():
    package = importlib.import_module("fmo.composition_stages")

    assert hasattr(package, "__path__")
    modules = {item.name for item in pkgutil.iter_modules(package.__path__)}
    assert {"discovery", "access"}.issubset(modules)
    assert "quota" not in modules

    discovery = importlib.import_module("fmo.composition_stages.discovery")
    access = importlib.import_module("fmo.composition_stages.access")

    assert inspect.getmodule(discovery._metadata_stage).__name__.endswith(".discovery")
    assert inspect.getmodule(discovery._free_candidate_stage).__name__.endswith(".discovery")
    assert inspect.getmodule(discovery._account_discovery_stage).__name__.endswith(".discovery")
    assert inspect.getmodule(discovery._model_matching_stage).__name__.endswith(".discovery")
    assert inspect.getmodule(access._access_classification_stage).__name__.endswith(".access")


@pytest.mark.spec("system-architecture::Probing, telemetry, inventory, and role stages live in dedicated modules")
@pytest.mark.spec("system-architecture::Middle-of-pipeline stages are defined in their own modules")
def test_runtime_composition_stages_live_in_dedicated_modules():
    stages = importlib.import_module("fmo.composition_stages")
    adapters = stages._production_stage_adapters()
    for name in ("probing", "telemetry-sync", "hermes-inventory", "role-lifecycle", "role-scoring"):
        assert name in adapters
        assert callable(adapters[name])

    probing = importlib.import_module("fmo.composition_stages.probing")
    telemetry = importlib.import_module("fmo.composition_stages.telemetry")
    inventory = importlib.import_module("fmo.composition_stages.inventory")
    roles = importlib.import_module("fmo.composition_stages.roles")

    assert inspect.getmodule(probing._probing_stage).__name__.endswith(".probing")
    assert inspect.getmodule(telemetry._telemetry_sync_stage).__name__.endswith(".telemetry")
    assert inspect.getmodule(inventory._hermes_inventory_stage).__name__.endswith(".inventory")
    assert inspect.getmodule(roles._role_lifecycle_stage).__name__.endswith(".roles")
    assert inspect.getmodule(roles._role_scoring_stage).__name__.endswith(".roles")


@pytest.mark.spec("system-architecture::Role scoring helpers move with the role stage")
def test_role_scoring_helpers_live_with_role_stage_module():
    roles = importlib.import_module("fmo.composition_stages.roles")

    for helper in (
        "_seed_quality_bands",
        "_quality_band_candidates",
        "_latest_aa_metrics_by_model",
        "_latest_health_by_endpoint",
        "_health_component",
        "_stability_component",
        "_latency_component",
        "_context_window_eligibility",
        "_quality_gate_eligibility",
        "_roles_needing_quality_recalibration",
        "_insert_health_observation",
    ):
        assert inspect.getmodule(getattr(roles, helper)).__name__.endswith(".roles")


@pytest.mark.spec("system-architecture::Allocation, apply, rollback, and audit stages live in dedicated modules")
@pytest.mark.spec("system-architecture::Each stage resolves to its own domain module")
def test_back_pipeline_stages_live_in_dedicated_modules():
    root_module = ROOT / "src" / "fmo" / "composition_stages.py"
    legacy_module = ROOT / "src" / "fmo" / "composition_stages" / "_legacy.py"
    assert not root_module.exists()
    assert not legacy_module.exists()

    stages = importlib.import_module("fmo.composition_stages")
    adapters = stages._production_stage_adapters()
    for name in ("demand-forecast", "allocation", "diff", "apply", "audit"):
        assert name in adapters
        assert callable(adapters[name])
    assert callable(stages._rollback_stage)

    allocation = importlib.import_module("fmo.composition_stages.allocation")
    apply = importlib.import_module("fmo.composition_stages.apply")
    rollback = importlib.import_module("fmo.composition_stages.rollback")
    audit = importlib.import_module("fmo.composition_stages.audit")

    assert inspect.getmodule(allocation._allocation_stage).__name__.endswith(".allocation")
    assert inspect.getmodule(allocation._demand_forecast_stage).__name__.endswith(".allocation")
    assert inspect.getmodule(apply._apply_stage).__name__.endswith(".apply")
    assert inspect.getmodule(apply._diff_stage).__name__.endswith(".apply")
    assert inspect.getmodule(rollback._rollback_stage).__name__.endswith(".rollback")
    assert inspect.getmodule(audit._audit_stage).__name__.endswith(".audit")


@pytest.mark.spec("system-architecture::Shared stage helpers live in one helpers module")
def test_shared_stage_helpers_live_in_helpers_module():
    helpers = importlib.import_module("fmo.composition_stages._helpers")

    for helper in (
        "_effect_result",
        "_adapter_stage",
        "_omniroute_instance_id",
    ):
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


@pytest.mark.spec("system-architecture::Timestamp and hashing helpers are centralized")
@pytest.mark.spec("system-architecture::Stage helpers carry no re-export alias layer")
def test_timestamp_hash_and_quota_helpers_are_centralized():
    idempotency = importlib.import_module("fmo.idempotency")
    access_state = importlib.import_module("fmo.access_state")
    stage_helpers = importlib.import_module("fmo.composition_stages._helpers")
    discovery = (ROOT / "src" / "fmo" / "composition_stages" / "discovery.py").read_text(encoding="utf-8")
    access = (ROOT / "src" / "fmo" / "composition_stages" / "access.py").read_text(encoding="utf-8")
    probing = (ROOT / "src" / "fmo" / "composition_stages" / "probing.py").read_text(encoding="utf-8")
    allocation = (ROOT / "src" / "fmo" / "composition_stages" / "allocation.py").read_text(encoding="utf-8")
    apply_stage = (ROOT / "src" / "fmo" / "composition_stages" / "apply.py").read_text(encoding="utf-8")
    roles = (ROOT / "src" / "fmo" / "composition_stages" / "roles.py").read_text(encoding="utf-8")
    stage_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "src" / "fmo" / "composition_stages").glob("*.py")
        if path.name != "__init__.py"
    )
    model_registration_source = (ROOT / "src" / "fmo" / "model_registration.py").read_text(encoding="utf-8")

    for helper in (
        "utcnow",
        "canonical_slug",
        "hash_parts",
        "combo_models_idempotency_key",
        "provider_model_idempotency_key",
    ):
        assert inspect.getmodule(getattr(idempotency, helper)).__name__ == "fmo.idempotency"
    assert inspect.getmodule(access_state.remaining_amount).__name__ == "fmo.access_state"
    old_aliases = [f"_{name}" for name in ("canonical_slug", "hash_parts")]
    old_aliases.append("_" + "remaining_" + "amount")
    for helper in old_aliases:
        assert not hasattr(stage_helpers, helper)

    assert "from fmo.idempotency import canonical_slug" in discovery
    assert "from fmo.idempotency import hash_parts" in probing
    assert "from fmo.idempotency import hash_parts" in allocation
    assert "from fmo.idempotency import hash_parts" in apply_stage
    assert "from fmo.idempotency import hash_parts" in roles
    assert "quota_normalize" not in access
    assert "from fmo.access_state import remaining_amount" in probing
    assert "from fmo.access_state import remaining_amount" in allocation
    assert "from fmo.access_state import remaining_amount" in apply_stage
    assert "from fmo.access_state import remaining_amount" in roles

    for old_definition in [rf"def {alias}\(" for alias in old_aliases]:
        assert re.search(old_definition, stage_source) is None
    assert re.search(r"def _combo_models_idempotency_key\(", stage_source) is None
    assert "datetime.now(UTC)" not in stage_source
    assert "def _idempotency_key" not in model_registration_source


@pytest.mark.spec("system-architecture::Test fakes live in a shared test-support module")
def test_composition_fakes_live_in_shared_test_support_module():
    clients = importlib.import_module("tests._clients")
    old_monolith = ROOT / "tests" / "test_composition.py"

    assert not old_monolith.exists()
    for fake in (
        "PipelineOpsClient",
        "MultiComboOpsClient",
        "AccountDiscoveryOpsClient",
        "RecordingLlmRuntime",
        "FakeOpenAIClient",
        "FakeInstructorCompletions",
        "FakeInstructorClient",
    ):
        assert inspect.getmodule(getattr(clients, fake)).__name__ == "tests._clients"


@pytest.mark.spec("system-architecture::Composition tests mirror the stage packages")
def test_composition_tests_mirror_stage_package_domains():
    expected = {
        "test_composition_discovery.py",
        "test_composition_access.py",
        "test_composition_runtime.py",
        "test_composition_apply.py",
    }
    test_files = {path.name for path in (ROOT / "tests").glob("test_composition*.py")}

    assert expected.issubset(test_files)
    assert "test_composition.py" not in test_files


@pytest.mark.spec("system-architecture::Test suite runs from both pytest entry points")
def test_pytest_entry_points_have_shared_import_path():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    tests_package = ROOT / "tests" / "__init__.py"

    assert tests_package.exists()
    assert 'pythonpath = ["src", ".", "tests"]' in pyproject
    assert "$(VENV)/pytest -q" in makefile
