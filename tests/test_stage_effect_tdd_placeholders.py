import pytest


@pytest.mark.xfail(reason="stage adapter wiring lands in subsequent OpenSpec slices", strict=True)
@pytest.mark.spec("combo-applier::Production apply smoke-tests applied combos")
@pytest.mark.spec("combo-applier::Fabricated smoke signal rejected")
@pytest.mark.spec("pipeline-orchestration::Production apply runs the real smoke test")
@pytest.mark.spec("pipeline-orchestration::Failing guard blocks apply")
@pytest.mark.spec("pipeline-orchestration::Smoke failure rolls back")
@pytest.mark.spec("pipeline-orchestration::Audit persists records")
def test_apply_audit_stage_effects_are_not_wired_yet():
    assert False
