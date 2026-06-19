from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.spec("runtime-documentation::Active docs state")
def test_runtime_docs_record_executable_scenario_policy_and_empty_pending_allowlist():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    pending_lines = [
        line.strip()
        for line in (ROOT / "tests" / "spec_coverage_pending.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]

    assert "Executable scenarios" in agents
    assert "@pytest.mark." + "spec(" in agents
    assert "<capability>::<Scenario name>" in agents
    assert pending_lines == []
