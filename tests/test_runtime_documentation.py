from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


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
    assert pending_lines
    assert "wire-hermes-inventory-source" in todo
    assert "wire-aa-index-cli-dispatch" in todo
    assert "wire-demand-forecast-and-role-lifecycle" in todo
    assert "repository methods" in completion_review
    assert "adapter-backed boundary" in completion_review
    assert "Active Slice Backlog" in todo
    assert "No deferred review follow-up work discovered." not in todo
    assert "Active review follow-up slices" not in todo
