from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
# Active proposal slices awaiting TDD implementation. Each entry is dropped from
# tests/spec_coverage_pending.txt (and here) when its test lands. Slices are
# listed in openspec/TODO.md and openspec/changes/<id>/.
EXPECTED_ACTIVE_PENDING = {
    # wire-account-discovery-stage
    "pipeline-orchestration::Account discovery persists quota pools",
    "pipeline-orchestration::Account discovery ordered before allocation inputs",
    "pipeline-orchestration::Unavailable rate-limit data stays conservative",
    "cli-and-operations::Discover-accounts command uses account discovery",
    # integrate-quality-and-context-gates
    "role-scorer::Below context minimum rejected in scoring",
    "role-scorer::Below quality gate rejected in scoring",
    "pipeline-orchestration::Scoring stage drops below-context endpoint",
    "pipeline-orchestration::Scoring stage drops below-gate endpoint",
    "pipeline-orchestration::Index-version mismatch keeps current combo",
    # harden-omniroute-retry-and-idempotency
    "omniroute-client::GET transient 5xx retried",
    "omniroute-client::GET network error retried",
    "omniroute-client::POST carries idempotency key and is not retried",
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
