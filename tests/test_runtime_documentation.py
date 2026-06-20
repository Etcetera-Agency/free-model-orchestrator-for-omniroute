from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_ACTIVE_PENDING = {
    "audit-rollback::rollback command reverts combos, not AA-index",
    "audit-rollback::rollback restore failure exits 7",
    "system-architecture::Refactor preserves behavior",
    "system-architecture::Stage domains live in separate modules",
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
    for change_id in (
        "route-rollback-command-to-combo-revert",
        "refactor-composition-into-stage-modules",
    ):
        assert change_id in todo
    assert "No deferred review follow-up work discovered outside the active slice queue." in todo
    assert "Active Slice Backlog" not in todo
    assert "Active review follow-up slices" not in todo
