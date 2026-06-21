from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
# Active proposal slices awaiting TDD implementation. Each entry is dropped from
# tests/spec_coverage_pending.txt (and here) when its test lands. Slices are
# listed in openspec/TODO.md and openspec/changes/<id>/.
EXPECTED_ACTIVE_PENDING = {
    # add-profile-combo-normalization
    "profile-normalization::Raw slot maps to combo with same canonical model",
    "profile-normalization::Missing combo falls back to default profile combo",
    "profile-normalization::Conforming and auto slots are untouched",
    "profile-normalization::Dry-run writes nothing and backs up config",
    "profile-normalization::Apply backs up before atomic rewrite",
    "cli-and-operations::Normalize command dispatches to normalization",
    "cli-and-operations::Normalize dry-run reports without writing",
    # trigger-quota-recalc-on-free-model-changes
    "quota-research::No new free model skips quota research",
    "quota-research::Recalc re-searches all on new free model",
    "quota-research::New model outside our connections does not trigger",
    "quota-research::Changed free status triggers recalc",
    "pipeline-orchestration::Quota research is triggered by new free models",
    "pipeline-orchestration::No new free model leaves quota research skipped",
    "pipeline-orchestration::Lost-free-status model is dropped on rebalance",
    # register-new-free-models-in-omniroute
    "model-registration::New free model under a connection is registered",
    "model-registration::Registration is idempotent and additive",
    "model-registration::Model outside our connections is skipped",
    "system-architecture::Registration is the only added write",
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
    assert "No deferred review follow-up work discovered." in todo
    assert "Active Slice Backlog" not in todo
    assert "Active review follow-up slices" not in todo


@pytest.mark.spec("system-architecture::Stage domains live in separate modules")
@pytest.mark.spec("system-architecture::Refactor preserves behavior")
def test_composition_root_is_thin_and_stage_domains_are_split():
    root = (ROOT / "src" / "fmo" / "composition.py").read_text(encoding="utf-8")
    stages = (ROOT / "src" / "fmo" / "composition_stages.py").read_text(encoding="utf-8")
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
